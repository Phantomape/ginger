from backtest_cash_ledger import CashEvent, DatedCashLedger, core_trade_cash_events


def test_dated_ledger_orders_exit_before_entry_and_conserves_cash():
    ledger = DatedCashLedger(100.0)
    ledger.book_all([
        CashEvent("2026-01-02", 20, "new", "core_entry", -80.0),
        CashEvent("2026-01-02", 10, "old", "core_exit", 50.0),
    ])
    assert [row["event_id"] for row in ledger.rows] == ["old", "new"]
    assert ledger.cash == 70.0
    assert ledger.audit()["cash_conservation_passed"]


def test_core_trade_events_preserve_net_pnl():
    events = core_trade_cash_events([{
        "trade_key": "ABC:2026-01-01:10", "ticker": "ABC",
        "entry_date": "2026-01-01", "exit_date": "2026-01-03",
        "entry_price": 10.0, "exit_price": 11.0, "shares": 5, "pnl": 4.5,
    }])
    ledger = DatedCashLedger(100.0)
    ledger.book_all(events)
    assert ledger.cash == 104.5
    assert not ledger.negative_cash_events


def test_negative_cash_is_explicit_not_silently_clipped():
    ledger = DatedCashLedger(100.0)
    ledger.book(CashEvent("2026-01-01", 20, "too-big", "core_entry", -125.0))
    assert ledger.cash == -25.0
    assert ledger.audit()["negative_cash_event_count"] == 1
