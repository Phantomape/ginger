"""Dated cash ledger for portfolio-level backtest composition.

The core backtester reports trade lifecycles but intentionally models risk
capital rather than settled cash.  This helper provides an explicit,
auditable cash view for experiments that may only deploy uncommitted cash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class CashEvent:
    date: str
    priority: int
    event_id: str
    kind: str
    amount: float
    metadata: dict[str, Any] = field(default_factory=dict)


class DatedCashLedger:
    """Book deterministic cash events and retain a complete audit trail."""

    def __init__(self, initial_cash: float) -> None:
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.rows: list[dict[str, Any]] = []
        self.negative_cash_events: list[dict[str, Any]] = []

    def book(self, event: CashEvent) -> dict[str, Any]:
        before = self.cash
        self.cash += float(event.amount)
        row = {
            "date": str(event.date)[:10],
            "priority": int(event.priority),
            "event_id": event.event_id,
            "kind": event.kind,
            "amount": round(float(event.amount), 8),
            "cash_before": round(before, 8),
            "cash_after": round(self.cash, 8),
            "metadata": dict(event.metadata),
        }
        self.rows.append(row)
        if self.cash < -1e-7:
            self.negative_cash_events.append(row)
        return row

    def book_all(self, events: Iterable[CashEvent]) -> list[dict[str, Any]]:
        return [self.book(event) for event in sorted(events, key=lambda e: (e.date, e.priority, e.event_id))]

    def audit(self) -> dict[str, Any]:
        event_sum = sum(float(row["amount"]) for row in self.rows)
        expected = self.initial_cash + event_sum
        error = self.cash - expected
        return {
            "initial_cash": round(self.initial_cash, 8),
            "ending_cash": round(self.cash, 8),
            "event_count": len(self.rows),
            "negative_cash_event_count": len(self.negative_cash_events),
            "negative_cash_events": self.negative_cash_events,
            "cash_conservation_error": round(error, 10),
            "cash_conservation_passed": abs(error) <= 1e-7,
        }


def core_trade_cash_events(trades: Iterable[dict[str, Any]]) -> list[CashEvent]:
    """Convert closed core rows to conservative dated cash events.

    Each closed row is treated as a separate lot.  This preserves partial
    reductions.  Add-on shares inherit the reported lifecycle entry date,
    which reserves their cash early and therefore cannot overstate cash
    available to a subordinate sleeve.
    """

    events: list[CashEvent] = []
    for index, trade in enumerate(trades):
        shares = float(trade.get("shares") or 0.0)
        entry = float(trade.get("entry_price") or 0.0)
        exit_price = float(trade.get("exit_price") or 0.0)
        if shares <= 0 or entry <= 0:
            continue
        key = str(trade.get("trade_key") or f"core-{index}") + f":lot-{index}"
        # Reported net PnL is the authoritative cost-aware lifecycle result.
        # Credit entry basis + net PnL so the ledger exactly preserves it.
        events.append(CashEvent(
            date=str(trade.get("exit_date"))[:10], priority=10,
            event_id=key + ":exit", kind="core_exit",
            amount=entry * shares + float(trade.get("pnl") or 0.0),
            metadata={"ticker": trade.get("ticker"), "shares": shares,
                      "reported_exit_price": exit_price},
        ))
        events.append(CashEvent(
            date=str(trade.get("entry_date"))[:10], priority=20,
            event_id=key + ":entry", kind="core_entry",
            amount=-(entry * shares),
            metadata={"ticker": trade.get("ticker"), "shares": shares},
        ))
    return events
