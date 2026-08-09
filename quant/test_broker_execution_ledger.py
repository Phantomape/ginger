"""Focused tests for the broker-authoritative execution ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import broker_execution_ledger as L


def _capture(
    *,
    collection_id: str = "capture-1",
    completed_at: str = "2026-07-11T20:00:01Z",
) -> dict:
    account_key = L.account_key(
        security_firm="FUTUSG", trade_environment="REAL", acc_id="283726803957104546"
    )
    return {
        "collection_id": collection_id,
        "collection_started_at_utc": "2026-07-11T20:00:00Z",
        "collection_completed_at_utc": completed_at,
        "account_key": account_key,
        "security_firm": "FUTUSG",
        "trade_environment": "REAL",
        "sdk_version": "10.07.6708",
        "history_start": "2024-07-11",
        "history_end": "2026-07-11",
        "queries": {
            "positions": {"status": "ok", "row_count": 1, "observed_at_utc": completed_at},
            "account": {"status": "ok", "row_count": 1, "observed_at_utc": completed_at},
            "history_deals": {"status": "ok", "row_count": 2, "observed_at_utc": completed_at},
            "history_orders": {"status": "ok", "row_count": 1, "observed_at_utc": completed_at},
            "order_fees": {"status": "ok", "row_count": 1, "observed_at_utc": completed_at},
            "cashflows": {"status": "ok", "row_count": 1, "observed_at_utc": completed_at},
        },
        "deals": [
            {
                "code": "US.AAPL",
                "stock_name": "Apple",
                "deal_market": "US",
                "deal_id": 283726803957104501,
                "order_id": 283726803957104500,
                "qty": 6,
                "price": 100.25,
                "trd_side": "BUY",
                "create_time": "2026-07-11 09:30:00.123",
                "status": "OK",
            },
            {
                "code": "US.AAPL",
                "stock_name": "Apple",
                "deal_market": "US",
                "deal_id": 283726803957104502,
                "order_id": 283726803957104500,
                "qty": 4,
                "price": 100.5,
                "trd_side": "BUY",
                "create_time": "2026-07-11 09:30:00.456",
                "status": "OK",
            },
        ],
        "orders": [
            {
                "code": "US.AAPL",
                "order_market": "US",
                "order_id": 283726803957104500,
                "trd_side": "BUY",
                "order_type": "NORMAL",
                "order_status": "FILLED_ALL",
                "qty": 10,
                "price": 100.5,
                "dealt_qty": 10,
                "dealt_avg_price": 100.35,
                "create_time": "2026-07-11 09:29:59.900",
                "updated_time": "2026-07-11 09:30:00.500",
                "currency": "USD",
            }
        ],
        "order_fees": [
            {
                "order_id": 283726803957104500,
                "fee_amount": 1.25,
                "fee_details": [("Commission", 1.0), ("Platform", 0.25)],
            }
        ],
        "cashflows": [
            {
                "cashflow_id": 283726803957104599,
                "clearing_date": "2026-07-11",
                "settlement_date": "2026-07-13",
                "currency": "USD",
                "cashflow_type": 1,
                "cashflow_direction": "OUT",
                "cashflow_amount": 1004.75,
                "cashflow_remark": "trade settlement",
                "create_time": "2026-07-11 18:00:00",
            }
        ],
        "accounts": [
            {
                "acc_id": 283726803957104546,
                "currency": "USD",
                "total_assets": 900.0,
                "cash": -100.0,
                "market_val": 1000.0,
                "long_mv": 1000.0,
                "short_mv": 0.0,
                "available_funds": -125.0,
                "power": 500.0,
            }
        ],
        "positions": [
            {
                "acc_id": 283726803957104546,
                "code": "US.AAPL",
                "position_id": 283726803957104588,
                "qty": 10,
                "average_cost": 100.35,
                "market_val": 1000.0,
                "position_side": "LONG",
                "currency": "USD",
            }
        ],
    }


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_account_key_is_stable_and_does_not_expose_raw_account_id():
    first = L.account_key(security_firm="FUTUSG", trade_environment="REAL", acc_id=123456)
    second = L.account_key(security_firm="FUTUSG", trade_environment="REAL", acc_id="123456")
    assert first == second
    assert "123456" not in first


def test_persist_is_idempotent_and_preserves_full_broker_facts(tmp_path):
    capture = _capture()
    first = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    second = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)

    assert first["ledgers"]["fills"]["rows_appended"] == 2
    assert first["ledgers"]["order_fees"]["rows_appended"] == 1
    assert all(row["rows_appended"] == 0 for row in second["ledgers"].values())

    fills = _jsonl(tmp_path / "fills.jsonl")
    fill = fills[0]["fact"]
    assert fill["deal_id"] == "283726803957104501"
    assert fill["order_id"] == "283726803957104500"
    assert fill["price"] == "100.25"
    assert fill["event_time_raw"] == "2026-07-11 09:30:00.123"
    assert fill["event_time_utc"] is None
    assert fill["event_time_timezone_status"] == "broker_local_unspecified"
    assert fill["fee_scope"] == "order_level_not_fill_level"

    fees = _jsonl(tmp_path / "order_fee_snapshots.jsonl")
    assert len(fees) == 1  # one order fee, despite two fills
    assert fees[0]["fact"]["currency"] == "USD"
    assert fees[0]["fact"]["fee_scope"] == "broker_reported_order_level"

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    exposure = state["latest_account_snapshot"]["exposure"]
    assert exposure["cash_reported"] == "-100"
    assert exposure["negative_cash_preserved"] is True
    assert state["fee_coverage"]["fill_order_count"] == 1
    assert state["fee_coverage"]["orders_with_reported_fee"] == 1
    assert state["fee_coverage"]["fill_fee_allocation"] == "not_performed"
    assert "283726803957104546" not in (tmp_path / "account_snapshots.jsonl").read_text(
        encoding="utf-8"
    )
    assert L.validate_broker_execution_ledger(tmp_path)["status"] == "valid"


def test_same_deal_id_correction_appends_version_without_overwriting_prefix(tmp_path):
    first = _capture()
    L.persist_broker_execution_capture(first, ledger_dir=tmp_path)
    path = tmp_path / "fills.jsonl"
    before = path.read_bytes()

    corrected = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    corrected["deals"][0]["price"] = 99.0
    corrected["deals"][0]["status"] = "CHANGED"
    result = L.persist_broker_execution_capture(corrected, ledger_dir=tmp_path)

    after = path.read_bytes()
    rows = _jsonl(path)
    assert after.startswith(before)
    assert result["ledgers"]["fills"]["rows_appended"] == 1
    assert len(rows) == 3
    assert result["state"]["deal_projection"]["distinct_deal_count"] == 2
    assert result["state"]["deal_projection"]["effective_deal_count"] == 2


def test_cancelled_latest_deal_version_is_kept_raw_but_voided_economically(tmp_path):
    first = _capture()
    first["deals"] = [first["deals"][0]]
    first["positions"][0]["qty"] = 6
    L.persist_broker_execution_capture(first, ledger_dir=tmp_path)

    cancelled = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    cancelled["deals"] = [dict(cancelled["deals"][0], status="CANCELLED")]
    cancelled["positions"] = []
    cancelled["queries"]["positions"]["row_count"] = 0
    result = L.persist_broker_execution_capture(cancelled, ledger_dir=tmp_path)

    projection = result["state"]["deal_projection"]
    assert projection["deal_snapshot_count"] == 2
    assert projection["distinct_deal_count"] == 1
    assert projection["effective_deal_count"] == 0
    assert projection["cancelled_deal_count"] == 1
    assert result["state"]["position_qty_reconciliation"]["status"] == "matched"
    assert result["state"]["lifecycle_replay"]["active_mapping_link_count"] == 0
    links = [row["fact"] for row in _jsonl(tmp_path / "fill_lifecycle_links.jsonl")]
    assert links[-1]["link_status"] == "void_cancelled"
    assert result["state"]["lifecycle_replay"]["void_latest_deal_link_count"] == 1


def test_corrupt_chain_is_rejected_without_repair_or_skip(tmp_path):
    L.persist_broker_execution_capture(_capture(), ledger_dir=tmp_path)
    path = tmp_path / "fills.jsonl"
    corrupted = path.read_text(encoding="utf-8").replace('"price":"100.25"', '"price":"101.25"')
    path.write_text(corrupted, encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(L.BrokerLedgerCorruptionError):
        L.persist_broker_execution_capture(
            _capture(collection_id="capture-2"), ledger_dir=tmp_path
        )
    assert path.read_bytes() == before


def test_validator_requires_collection_manifest_for_nonempty_ledger(tmp_path):
    L.persist_broker_execution_capture(_capture(), ledger_dir=tmp_path)
    (tmp_path / "collection_manifests.jsonl").unlink()
    with pytest.raises(L.BrokerLedgerCorruptionError, match="collection manifest"):
        L.validate_broker_execution_ledger(tmp_path)


def test_same_collection_snapshot_conflict_fails_before_any_write(tmp_path):
    capture = _capture()
    L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.glob("*.jsonl")}
    conflicting = _capture()  # same collection identity
    conflicting["accounts"][0]["cash"] = 999.0

    with pytest.raises(L.BrokerLedgerConflictError):
        L.persist_broker_execution_capture(conflicting, ledger_dir=tmp_path)
    assert {path.name: path.read_bytes() for path in tmp_path.glob("*.jsonl")} == before


def test_second_account_is_rejected_from_account_scoped_ledger(tmp_path):
    L.persist_broker_execution_capture(_capture(), ledger_dir=tmp_path)
    other = _capture(collection_id="capture-other")
    other["account_key"] = L.account_key(
        security_firm="FUTUSG", trade_environment="REAL", acc_id="different-account"
    )
    with pytest.raises(L.BrokerLedgerConflictError, match="account-scoped"):
        L.persist_broker_execution_capture(other, ledger_dir=tmp_path)


def test_fee_pending_is_unknown_and_later_report_is_a_new_version(tmp_path):
    pending = _capture()
    pending["order_fees"][0]["fee_amount"] = "N/A"
    pending["order_fees"][0]["fee_details"] = []
    L.persist_broker_execution_capture(pending, ledger_dir=tmp_path)

    reported = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    result = L.persist_broker_execution_capture(reported, ledger_dir=tmp_path)
    fee_rows = _jsonl(tmp_path / "order_fee_snapshots.jsonl")

    assert result["ledgers"]["order_fees"]["rows_appended"] == 1
    assert len(fee_rows) == 2
    assert fee_rows[0]["fact"]["fee_amount"] is None
    assert fee_rows[0]["fact"]["fee_status"] == "pending_or_unavailable"
    assert fee_rows[1]["fact"]["fee_amount"] == "1.25"


def test_sdk_upgrade_is_collection_metadata_not_bulk_fact_revision(tmp_path):
    L.persist_broker_execution_capture(_capture(), ledger_dir=tmp_path)
    upgraded = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    upgraded["sdk_version"] = "10.08.0000"
    result = L.persist_broker_execution_capture(upgraded, ledger_dir=tmp_path)

    for surface in ("fills", "orders", "order_fees", "cashflows", "lifecycle_links"):
        assert result["ledgers"][surface]["rows_appended"] == 0
    assert result["ledgers"]["collections"]["rows_appended"] == 1
    assert result["state"]["cashflow_projection"]["distinct_cashflow_count"] == 1


def test_same_day_close_and_reopen_have_distinct_lifecycles(tmp_path):
    capture = _capture()
    capture["deals"] = [
        {
            "code": "US.SNXX", "deal_market": "US", "deal_id": "1", "order_id": "11",
            "qty": 10, "price": 20, "trd_side": "BUY",
            "create_time": "2026-07-11 09:30:00.000", "status": "OK",
        },
        {
            "code": "US.SNXX", "deal_market": "US", "deal_id": "2", "order_id": "12",
            "qty": 10, "price": 21, "trd_side": "SELL",
            "create_time": "2026-07-11 10:00:00.000", "status": "OK",
        },
        {
            "code": "US.SNXX", "deal_market": "US", "deal_id": "3", "order_id": "13",
            "qty": 5, "price": 22, "trd_side": "BUY",
            "create_time": "2026-07-11 10:00:00.001", "status": "OK",
        },
    ]
    capture["orders"] = []
    capture["order_fees"] = []
    capture["cashflows"] = []
    capture["positions"] = [
        {"code": "US.SNXX", "position_id": "reused", "qty": 5,
         "average_cost": 22, "market_val": 110, "position_side": "LONG"}
    ]
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    links = [row["fact"] for row in _jsonl(tmp_path / "fill_lifecycle_links.jsonl")]

    assert [row["event_role"] for row in links] == ["open", "close", "open"]
    assert links[0]["lifecycle_id"] == links[1]["lifecycle_id"]
    assert links[2]["lifecycle_id"] != links[0]["lifecycle_id"]
    assert result["state"]["lifecycle_replay"]["closed_lifecycle_count"] == 1
    assert result["state"]["lifecycle_replay"]["current_lifecycles"]["US.SNXX"][
        "lifecycle_start_deal_id"
    ] == "3"


def test_future_fill_appends_only_one_prefix_stable_lifecycle_link(tmp_path):
    first = _capture()
    L.persist_broker_execution_capture(first, ledger_dir=tmp_path)
    later = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    later["deals"].append(
        {
            "code": "US.AAPL", "deal_market": "US", "deal_id": "new-deal",
            "order_id": "new-order", "qty": 1, "price": 101,
            "trd_side": "SELL", "create_time": "2026-07-11 10:30:00", "status": "OK",
        }
    )
    later["positions"][0]["qty"] = 9

    result = L.persist_broker_execution_capture(later, ledger_dir=tmp_path)
    assert result["ledgers"]["fills"]["rows_appended"] == 1
    assert result["ledgers"]["lifecycle_links"]["rows_appended"] == 1
    assert result["state"]["lifecycle_replay"]["active_mapping_link_count"] == 3


def test_no_position_anchor_never_promotes_apparent_flat_boundary(tmp_path):
    capture = _capture()
    capture["deals"] = [
        dict(capture["deals"][0], deal_id="1", qty=2, trd_side="BUY"),
        dict(capture["deals"][1], deal_id="2", qty=2, trd_side="SELL"),
    ]
    capture["positions"] = []
    capture["queries"]["positions"] = {
        "status": "error", "row_count": 0, "error": "unavailable"
    }
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    links = [row["fact"] for row in _jsonl(tmp_path / "fill_lifecycle_links.jsonl")]

    assert all(row["link_status"] == "unlinked_baseline_unknown" for row in links)
    assert result["state"]["lifecycle_replay"]["closed_lifecycle_count"] == 0
    assert result["state"]["lifecycle_replay"]["unlinked_count"] == 2


def test_unknown_window_baseline_never_promotes_derived_zero_to_trusted(tmp_path):
    capture = _capture()
    base = capture["deals"][0]
    capture["deals"] = [
        dict(base, deal_id="1", qty=1, trd_side="SELL",
             create_time="2026-07-11 09:30:00.000"),
        dict(base, deal_id="2", qty=1, trd_side="BUY",
             create_time="2026-07-11 09:31:00.000"),
        dict(base, deal_id="3", qty=1, trd_side="BUY",
             create_time="2026-07-11 09:32:00.000"),
    ]
    # Net fills are +1 while broker is +2, so the implied window baseline is
    # +1 and cannot prove where an unobserved transfer/action occurred.
    capture["positions"][0]["qty"] = 2
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    links = [row["fact"] for row in _jsonl(tmp_path / "fill_lifecycle_links.jsonl")]

    assert all(row["link_status"] == "unlinked_baseline_unknown" for row in links)
    assert result["state"]["lifecycle_replay"]["trusted_closed_lifecycle_count"] == 0


def test_cross_zero_quarantine_propagates_until_verified_flat_boundary(tmp_path):
    capture = _capture()
    base = capture["deals"][0]
    capture["deals"] = [
        dict(base, deal_id="1", order_id="1", qty=10, trd_side="BUY",
             create_time="2026-07-11 09:30:00.000"),
        dict(base, deal_id="2", order_id="2", qty=15, trd_side="SELL",
             create_time="2026-07-11 09:31:00.000"),
        dict(base, deal_id="3", order_id="3", qty=5, trd_side="BUY",
             create_time="2026-07-11 09:32:00.000"),
        dict(base, deal_id="4", order_id="4", qty=2, trd_side="BUY",
             create_time="2026-07-11 09:33:00.000"),
    ]
    capture["positions"][0]["qty"] = 2
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    links = [row["fact"] for row in _jsonl(tmp_path / "fill_lifecycle_links.jsonl")]

    assert [row["link_status"] for row in links] == [
        "linked", "ambiguous_cross_zero", "ambiguous_until_flat", "linked"
    ]
    assert links[2]["lifecycle_id"] is None
    assert links[3]["event_role"] == "open"
    assert result["state"]["lifecycle_replay"]["unlinked_count"] == 2


def test_successful_flat_position_query_appends_explicit_flat_snapshot(tmp_path):
    capture = _capture()
    capture["positions"] = []
    capture["queries"]["positions"]["row_count"] = 0
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    position = result["state"]["latest_position_snapshot"]
    assert position["position_count"] == 0
    assert position["flat_account_observed"] is True


def test_failed_account_and_position_queries_do_not_write_fake_empty_snapshots(tmp_path):
    capture = _capture()
    capture["accounts"] = []
    capture["positions"] = []
    capture["queries"]["account"] = {
        "status": "error", "row_count": 0, "error": "unavailable"
    }
    capture["queries"]["positions"] = {
        "status": "error", "row_count": 0, "error": "unavailable"
    }
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    assert result["ledgers"]["accounts"]["rows_total"] == 0
    assert result["ledgers"]["positions"]["rows_total"] == 0
    assert result["state"]["status"] == "partial_collection"


def test_successful_zero_row_account_query_does_not_create_fake_account_snapshot(
    tmp_path,
):
    capture = _capture()
    capture["accounts"] = []
    capture["queries"]["account"] = {"status": "ok", "row_count": 0, "error": None}
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    assert result["ledgers"]["accounts"]["rows_total"] == 0
    assert result["state"]["latest_account_snapshot"] is None
    assert result["state"]["latest_account_snapshot_is_current_collection"] is False


def test_account_snapshot_does_not_invent_zero_position_exposure_after_query_failure(
    tmp_path,
):
    capture = _capture()
    capture["positions"] = []
    capture["queries"]["positions"] = {
        "status": "error", "row_count": 0, "error": "position query unavailable"
    }
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    exposure = result["state"]["latest_account_snapshot"]["exposure"]

    assert exposure["position_exposure_status"] == "unavailable_position_query_failed"
    assert exposure["position_gross_market_value"] is None
    assert exposure["position_vs_account_market_value_delta"] is None
    assert result["state"]["position_qty_reconciliation"]["status"] == (
        "unavailable_position_query_failed"
    )


def test_cross_currency_position_totals_are_grouped_and_not_summed_without_fx(tmp_path):
    capture = _capture()
    capture["positions"][0]["currency"] = "EUR"
    result = L.persist_broker_execution_capture(capture, ledger_dir=tmp_path)
    exposure = result["state"]["latest_account_snapshot"]["exposure"]

    assert exposure["position_exposure_status"] == "suppressed_cross_currency_no_fx"
    assert exposure["position_gross_market_value"] is None
    assert exposure["position_market_value_by_currency"]["EUR"][
        "gross_market_value"
    ] == "1000"


def test_failed_new_account_query_marks_prior_snapshot_as_not_current(tmp_path):
    first = _capture()
    L.persist_broker_execution_capture(first, ledger_dir=tmp_path)
    second = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    second["accounts"] = []
    second["queries"]["account"] = {
        "status": "error", "row_count": 0, "error": "account query unavailable"
    }

    result = L.persist_broker_execution_capture(second, ledger_dir=tmp_path)
    state = result["state"]
    assert state["latest_account_snapshot"]["collection_id"] == "capture-1"
    assert state["latest_account_snapshot_is_current_collection"] is False
    assert state["latest_position_snapshot_is_current_collection"] is True


def test_atomic_write_failure_preserves_existing_prefix(tmp_path, monkeypatch):
    L.persist_broker_execution_capture(_capture(), ledger_dir=tmp_path)
    path = tmp_path / "fills.jsonl"
    before = path.read_bytes()
    later = _capture(collection_id="capture-2", completed_at="2026-07-11T21:00:00Z")
    later["deals"].append(
        {
            "code": "US.MSFT", "deal_market": "US", "deal_id": "new-deal",
            "order_id": "new-order", "qty": 1, "price": 500,
            "trd_side": "BUY", "create_time": "2026-07-11 10:30:00", "status": "OK",
        }
    )

    def fail_write(*args, **kwargs):
        raise PermissionError("simulated final rename failure")

    monkeypatch.setattr(L, "atomic_write_text", fail_write)
    with pytest.raises(PermissionError):
        L.persist_broker_execution_capture(later, ledger_dir=tmp_path)
    assert path.read_bytes() == before
