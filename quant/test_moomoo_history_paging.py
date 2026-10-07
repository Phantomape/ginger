"""Synthetic SDK boundary tests for full-window broker history collection."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import sys
from types import SimpleNamespace

import pytest

import broker_execution_ledger as L
import moomoo_open_positions as M


class Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        return self.rows


class FrozenClock(datetime):
    calls = 0

    @classmethod
    def now(cls, tz=None):
        cls.calls += 1
        return cls(2026, 9, 6, 12, tzinfo=timezone.utc)


class Broker:
    def __init__(self, fail_segment=None):
        self.calls = {"deals": [], "orders": [], "fee_ids": []}
        self.fail_segment = fail_segment
        self.closed = False
        self.history_deals = []
        self.current_deals = []
        self.history_orders = []
        self.current_orders = []

    def _history(self, kind, start, end):
        self.calls[kind].append((start, end))
        if (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 > 360:
            return -1, "single query cannot exceed 360 days"
        if self.fail_segment == "all" or len(self.calls[kind]) == self.fail_segment:
            return -1, "synthetic segment failure"
        return 0, Frame([row for row in getattr(self, "history_" + kind)
                         if start <= row["create_time"][:10] <= end])

    def history_deal_list_query(self, *, start, end, **kwargs):
        return self._history("deals", start, end)

    def history_order_list_query(self, *, start, end, **kwargs):
        return self._history("orders", start, end)

    def deal_list_query(self, **kwargs):
        return 0, Frame(self.current_deals)

    def order_list_query(self, **kwargs):
        return 0, Frame(self.current_orders)

    def position_list_query(self, **kwargs):
        return 0, Frame([])

    def accinfo_query(self, **kwargs):
        return 0, Frame([{"cash": 100, "total_assets": 100, "market_val": 0}])

    def get_acc_cash_flow(self, **kwargs):
        return 0, Frame([])

    def order_fee_query(self, *, order_id_list, **kwargs):
        self.calls["fee_ids"].extend(order_id_list)
        return 0, Frame([{"order_id": value, "fee_amount": 1} for value in order_id_list])

    def close(self):
        self.closed = True


def fetch(monkeypatch, broker, lookback=730):
    sdk = SimpleNamespace(
        OpenSecTradeContext=lambda **kwargs: broker,
        TrdMarket=SimpleNamespace(NONE="NONE"), TrdEnv=SimpleNamespace(REAL="REAL"),
        SecurityFirm=SimpleNamespace(FUTUSG="FUTUSG"), Currency=SimpleNamespace(USD="USD"), RET_OK=0,
    )
    monkeypatch.setitem(sys.modules, "moomoo", sdk)
    monkeypatch.setattr(M, "_opend_reachable", lambda *args: True)
    monkeypatch.setattr(M, "_redirect_moomoo_sdk_appdata", lambda: None)
    monkeypatch.setattr(M, "_restore_moomoo_sdk_appdata", lambda previous: None)
    monkeypatch.setattr(M, "datetime", FrozenClock)
    FrozenClock.calls = 0
    return M.fetch_moomoo_state(acc_id=123, fills_lookback_days=lookback, cashflow_lookback_days=1)


@pytest.mark.parametrize("lookback", [0, 359, 360, 730])
def test_full_inclusive_window_is_covered_exactly_once(monkeypatch, lookback):
    broker = Broker()
    state = fetch(monkeypatch, broker, lookback)
    capture = state["broker_execution"]
    start = date(2026, 9, 6) - timedelta(days=lookback)
    expected = [start + timedelta(days=i) for i in range(lookback + 1)]
    for kind, name in (("deals", "history_deals"), ("orders", "history_orders")):
        actual = []
        for left, right in broker.calls[kind]:
            left, right = date.fromisoformat(left), date.fromisoformat(right)
            assert 1 <= (right - left).days + 1 <= 360
            actual.extend(left + timedelta(days=i) for i in range((right - left).days + 1))
        assert actual == expected
        assert capture["queries"][name]["status"] == "ok"
    assert FrozenClock.calls == 1
    assert broker.closed


def test_both_sides_of_segment_boundary_are_retained(monkeypatch):
    broker = Broker()
    first = date(2026, 9, 6) - timedelta(days=730)
    days = [first, first + timedelta(days=359), first + timedelta(days=360), date(2026, 9, 6)]
    broker.history_deals = [{"deal_id": str(i), "order_id": str(i), "create_time": day.isoformat(), "status": "OK"}
                            for i, day in enumerate(days)]
    result = fetch(monkeypatch, broker)
    assert [row["deal_id"] for row in result["broker_execution"]["deals"]] == ["0", "1", "2", "3"]


@pytest.mark.parametrize("failed,status", [(1, "partial"), (2, "partial"), (3, "partial"), ("all", "error")])
def test_failed_segments_cannot_be_hidden_by_last_success(monkeypatch, failed, status):
    broker = Broker(fail_segment=failed)
    capture = fetch(monkeypatch, broker)["broker_execution"]
    manifest = L._safe_query_manifest(capture)
    for name in ("history_deals", "history_orders"):
        assert manifest[name]["status"] == status
        segments = {key: value for key, value in manifest.items() if key.startswith(name + ":")}
        assert len(segments) == 3
        assert sum(row["status"] == "error" for row in segments.values()) == (3 if failed == "all" else 1)
        assert all(".." in key for key in segments)


def test_current_versions_win_and_fee_order_ids_remain_unique(monkeypatch):
    broker = Broker()
    common = {"deal_id": "deal", "order_id": "order", "create_time": "2026-01-01", "status": "OK", "qty": 1}
    broker.history_deals = [dict(common), dict(common, status="CHANGED", qty=2)]
    broker.current_deals = [dict(common)]  # same as first version, latest broker observation wins
    order = {"order_id": "order", "create_time": "2026-01-01", "updated_time": "2026-06-01", "dealt_qty": 2}
    broker.history_orders = [order]
    broker.current_orders = [dict(order, updated_time="2026-05-01", dealt_qty=1)]
    result = fetch(monkeypatch, broker)
    capture = result["broker_execution"]
    assert result["fills"][0]["qty"] == 1
    assert capture["deals"][-1]["qty"] == 1
    assert capture["orders"][-1]["dealt_qty"] == 1
    assert Counter(broker.calls["fee_ids"]) == {"order": 1}


def test_current_cancellation_remains_last_and_not_effective(monkeypatch):
    broker = Broker()
    row = {"deal_id": "cancelled", "order_id": "order", "create_time": "2026-01-01", "status": "OK", "qty": 1}
    broker.history_deals = [row]
    broker.current_deals = [dict(row, status="CANCELLED")]
    result = fetch(monkeypatch, broker)
    assert result["fills"] == []
    assert result["broker_execution"]["deals"][-1]["status"] == "CANCELLED"
