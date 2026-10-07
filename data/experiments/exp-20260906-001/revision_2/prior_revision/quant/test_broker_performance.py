"""Synthetic broker facts only; never read the local account's real ledger."""

from copy import deepcopy
import hashlib
import json

import pytest

import broker_execution_ledger as L
from broker_performance import compute_broker_performance


def _capture(collection_id="c1"):
    deals = [
        {"deal_id": "d1", "order_id": "buy", "qty": 6, "price": 100, "trd_side": "BUY", "create_time": "2026-07-01 09:30:00"},
        {"deal_id": "d2", "order_id": "buy", "qty": 4, "price": 100, "trd_side": "BUY", "create_time": "2026-07-01 09:31:00"},
        {"deal_id": "d3", "order_id": "sell", "qty": 10, "price": 110, "trd_side": "SELL", "create_time": "2026-07-02 09:30:00"},
    ]
    return {
        "collection_id": collection_id,
        "collection_started_at_utc": "2026-07-03T20:00:00Z",
        "collection_completed_at_utc": "2026-07-03T20:00:01Z",
        "account_key": "synthetic-account",
        "security_firm": "SYNTHETIC",
        "trade_environment": "SIMULATE",
        "queries": {name: {"status": "ok"} for name in ("positions", "history_deals", "history_orders", "order_fees")},
        "deals": [dict(row, code="US.AAPL", deal_market="US", status="OK") for row in deals],
        "orders": [{"order_id": oid, "code": "US.AAPL", "currency": "USD", "dealt_qty": 10} for oid in ("buy", "sell")],
        "order_fees": [{"order_id": "buy", "fee_amount": 2}, {"order_id": "sell", "fee_amount": 3}],
        "positions": [],
    }


def _persist(tmp_path, capture=None):
    L.persist_broker_execution_capture(capture or _capture(), ledger_dir=tmp_path)


def _usd(summary):
    return summary["pnl_by_currency"]["USD"]


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rewrite_chain(path, rows):
    """Create intentionally incomplete but cryptographically valid test facts."""
    previous = None
    for index, row in enumerate(rows, 1):
        row["ledger_sequence"] = index
        row["prev_record_hash"] = previous
        row["fact_hash"] = L._sha256_json(row["fact"])
        row.pop("record_hash", None)
        previous = row["record_hash"] = L._sha256_json(row)
    path.write_text("".join(L._canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def test_partial_fills_fee_once_and_read_only_idempotency(tmp_path):
    _persist(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    first = compute_broker_performance(tmp_path)
    second = compute_broker_performance(tmp_path)
    assert first == second
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    assert first["status"] == "ok"
    assert first["counts"]["evaluated_lifecycle_count"] == 1
    assert _usd(first) == {"gross_trading_pnl_before_order_fees": 100.0, "order_fee_total": 5.0,
                           "net_trading_pnl_after_order_fees": 95.0, "evaluated_lifecycle_count": 1}
    assert first["trade_enabled"] is False
    assert first["strategy_attribution_status"] == "unavailable_no_decision_order_lineage"
    assert first["source_hashes"]["fills.jsonl"] == hashlib.sha256(before["fills.jsonl"]).hexdigest()
    json.dumps(first, allow_nan=False)


def test_latest_fill_and_fee_revision_replace_old_versions(tmp_path):
    _persist(tmp_path)
    revised = _capture("c2")
    revised["deals"][0].update(price=101, status="CHANGED")
    revised["order_fees"][0]["fee_amount"] = 4
    _persist(tmp_path, revised)
    result = compute_broker_performance(tmp_path)
    assert result["status"] == "ok"
    assert result["counts"]["effective_fill_count"] == 3
    assert _usd(result)["net_trading_pnl_after_order_fees"] == 87.0


def test_cancelled_fill_is_not_economic_and_remaining_orders_reconcile(tmp_path):
    _persist(tmp_path)
    revised = _capture("c2")
    revised["deals"][0]["status"] = "CANCELLED"
    revised["deals"][2].update(qty=4, status="CHANGED")
    for order in revised["orders"]:
        order["dealt_qty"] = 4
    _persist(tmp_path, revised)
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["cancelled_fill_count"] == 1
    assert result["counts"]["effective_fill_count"] == 2
    assert _usd(result)["net_trading_pnl_after_order_fees"] == 35.0


@pytest.mark.parametrize("missing", [None, "N/A"])
def test_missing_fee_never_becomes_zero(tmp_path, missing):
    capture = _capture()
    if missing is None:
        capture["order_fees"] = capture["order_fees"][:1]
    else:
        capture["order_fees"][1]["fee_amount"] = missing
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["status"] == "unavailable"
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None
    assert result["coverage_reasons"]["missing_order_fee_lifecycles"] == 1


def test_latest_pending_fee_does_not_reuse_earlier_reported_fee(tmp_path):
    _persist(tmp_path)
    revised = _capture("c2")
    revised["order_fees"][0]["fee_amount"] = "N/A"
    _persist(tmp_path, revised)
    assert _usd(compute_broker_performance(tmp_path))["net_trading_pnl_after_order_fees"] is None


@pytest.mark.parametrize("currency", [None, "HKD"])
def test_unknown_or_unsupported_currency_excluded(tmp_path, currency):
    capture = _capture()
    for order in capture["orders"]:
        order["currency"] = currency
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"]["unsupported_or_unknown_fill_currency_lifecycles"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


@pytest.mark.parametrize("code", ["US.AAPL260918C200000", "HK.00700", "FUT.ES"])
def test_derivatives_and_unsupported_markets_excluded(tmp_path, code):
    capture = _capture()
    for row in capture["deals"] + capture["orders"]:
        row["code"] = code
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"]["unsupported_instrument_lifecycles"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_missing_latest_link_cannot_create_a_partial_lifecycle_profit(tmp_path):
    _persist(tmp_path)
    path = tmp_path / "fill_lifecycle_links.jsonl"
    _rewrite_chain(path, _rows(path)[1:])
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["unlinked_fill_count"] == 1
    assert result["counts"]["excluded_lifecycle_count"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


@pytest.mark.parametrize("field,value", [("fill_identity_key", "stale-fill-version"), ("rule_version", "stale-rule")])
def test_latest_mismatched_link_never_falls_back_to_older_good_link(tmp_path, field, value):
    _persist(tmp_path)
    path = tmp_path / "fill_lifecycle_links.jsonl"
    rows = _rows(path)
    broken = deepcopy(rows[0])
    broken["identity_key"] += "|bad-latest"
    broken["fact"][field] = value
    _rewrite_chain(path, rows + [broken])
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["excluded_lifecycle_count"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_orphan_revisions_are_invisible(tmp_path):
    _persist(tmp_path)
    manifest_path = tmp_path / "collection_manifests.jsonl"
    committed_bytes = manifest_path.read_bytes()
    revised = _capture("orphan")
    revised["deals"][0].update(price=200, status="CHANGED")
    revised["order_fees"][0]["fee_amount"] = 7
    _persist(tmp_path, revised)
    manifest_path.write_bytes(committed_bytes)
    result = compute_broker_performance(tmp_path)
    assert result["status"] == "partial"
    assert result["counts"]["committed_collection_count"] == 1
    assert result["counts"]["uncommitted_row_count"] > 0
    assert _usd(result)["net_trading_pnl_after_order_fees"] == 95.0


def test_no_manifest_makes_all_rows_invisible(tmp_path):
    _persist(tmp_path)
    (tmp_path / "collection_manifests.jsonl").unlink()
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"]["no_committed_collections"] == 1
    assert result["counts"]["effective_fill_count"] == 0
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_corrupt_unrelated_chain_also_fails_closed_without_write(tmp_path):
    _persist(tmp_path)
    path = tmp_path / "position_snapshots.jsonl"
    path.write_bytes(path.read_bytes() + b"corrupt\n")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"] == {"ledger_corrupt_or_unreadable": 1}
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}


def test_open_lifecycle_is_not_realized_profit(tmp_path):
    capture = _capture()
    capture["deals"] = capture["deals"][:2]
    capture["positions"] = [{"code": "US.AAPL", "qty": 10, "position_side": "LONG"}]
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["open_lifecycle_count"] == 1
    assert result["counts"]["closed_lifecycle_count"] == 0
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_unknown_baseline_is_never_reconstructed_as_zero(tmp_path):
    capture = _capture()
    capture["positions"] = [{"code": "US.AAPL", "qty": 7, "position_side": "LONG"}]
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["unlinked_fill_count"] == 3
    assert result["coverage_reasons"]["unknown_position_baseline_fills"] == 3
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_cross_zero_has_no_synthetic_close(tmp_path):
    capture = _capture()
    capture["deals"][2]["qty"] = 15
    capture["orders"][1]["dealt_qty"] = 15
    capture["positions"] = [{"code": "US.AAPL", "qty": 5, "position_side": "SHORT"}]
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["evaluated_lifecycle_count"] == 0
    assert result["coverage_reasons"]["ambiguous_cross_zero_lifecycles"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_order_quantity_must_exactly_reconcile(tmp_path):
    capture = _capture()
    capture["orders"][0]["dealt_qty"] = 11
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"]["order_quantity_mismatch_lifecycles"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_order_spanning_lifecycles_excluded_instead_of_fee_allocation(tmp_path):
    capture = _capture()
    extra = deepcopy(capture["deals"])
    for i, row in enumerate(extra):
        row["deal_id"] = "e" + str(i)
        row["create_time"] = row["create_time"].replace("07-01", "07-03").replace("07-02", "07-04")
    capture["deals"] += extra
    for order in capture["orders"]:
        order["dealt_qty"] = 20
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["closed_lifecycle_count"] == 2
    assert result["counts"]["excluded_lifecycle_count"] == 2
    assert result["coverage_reasons"]["order_spans_untrusted_or_other_lifecycle_lifecycles"] == 2


def test_missing_directory_is_unavailable_and_not_created(tmp_path):
    absent = tmp_path / "not-created"
    result = compute_broker_performance(absent)
    assert result["status"] == "unavailable"
    assert not absent.exists()
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_partial_coverage_sums_only_the_same_fully_covered_cohort(tmp_path):
    capture = _capture()
    uncovered = deepcopy(capture)
    for row in uncovered["deals"]:
        row.update(code="US.MSFT", order_id="u-" + row["order_id"], deal_id="u-" + row["deal_id"])
    for order in uncovered["orders"]:
        order.update(code="US.MSFT", order_id="u-" + order["order_id"])
    capture["deals"] += uncovered["deals"]
    capture["orders"] += uncovered["orders"]
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["status"] == "partial"
    assert result["counts"]["closed_lifecycle_count"] == 2
    assert result["counts"]["evaluated_lifecycle_count"] == 1
    assert result["counts"]["excluded_lifecycle_count"] == 1
    assert _usd(result)["gross_trading_pnl_before_order_fees"] == 100.0
    assert _usd(result)["net_trading_pnl_after_order_fees"] == 95.0


def test_replay_link_prefix_cannot_incorporate_invisible_orphan_fill(tmp_path):
    _persist(tmp_path)
    path = tmp_path / "fill_lifecycle_links.jsonl"
    rows = _rows(path)
    for row in rows:
        row["fact"]["mapping_input_prefix_hash"] = "hash-from-orphan-inclusive-replay"
    _rewrite_chain(path, rows)
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"]["lifecycle_input_prefix_mismatch_lifecycles"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_non_atomic_collection_view_is_unavailable(tmp_path, monkeypatch):
    _persist(tmp_path)
    original = L._strict_read_chain

    def mutate_after_read(path):
        result = original(path)
        if path.name == "fills.jsonl":
            path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(L, "_strict_read_chain", mutate_after_read)
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"] == {"source_changed_during_read": 1}
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_missing_fee_currency_is_not_inferred_from_known_fill_currency(tmp_path):
    _persist(tmp_path)
    path = tmp_path / "order_fee_snapshots.jsonl"
    rows = _rows(path)
    rows[0]["fact"]["currency"] = None
    _rewrite_chain(path, rows)
    result = compute_broker_performance(tmp_path)
    assert result["coverage_reasons"]["unsupported_or_unknown_fee_currency_lifecycles"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_unknown_status_is_quarantined_even_if_cached_economic_flag_claims_effective(tmp_path):
    _persist(tmp_path)
    path = tmp_path / "fills.jsonl"
    rows = _rows(path)
    rows[0]["fact"]["deal_status"] = "PENDING"
    _rewrite_chain(path, rows)
    result = compute_broker_performance(tmp_path)
    assert result["counts"]["unknown_status_fill_count"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] is None


def test_later_valid_flat_lifecycle_survives_earlier_cross_zero_quarantine(tmp_path):
    capture = _capture()
    capture["deals"][2]["qty"] = 15
    capture["orders"][1]["dealt_qty"] = 15
    template = capture["deals"][0]
    capture["deals"] += [
        dict(template, deal_id="d4", order_id="cover", qty=5, create_time="2026-07-03 09:30:00"),
        dict(template, deal_id="d5", order_id="new-buy", qty=10, create_time="2026-07-04 09:30:00"),
        dict(template, deal_id="d6", order_id="new-sell", qty=10, price=120, trd_side="SELL", create_time="2026-07-05 09:30:00"),
    ]
    for oid, qty in (("cover", 5), ("new-buy", 10), ("new-sell", 10)):
        capture["orders"].append({"order_id": oid, "code": "US.AAPL", "currency": "USD", "dealt_qty": qty})
        capture["order_fees"].append({"order_id": oid, "fee_amount": 1})
    _persist(tmp_path, capture)
    result = compute_broker_performance(tmp_path)
    assert result["status"] == "partial"
    assert result["counts"]["evaluated_lifecycle_count"] == 1
    assert _usd(result)["net_trading_pnl_after_order_fees"] == 198.0
