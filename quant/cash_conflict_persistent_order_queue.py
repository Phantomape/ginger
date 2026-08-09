"""Pure FIFO state machine for settled-cash entry conflicts.

The helper deliberately knows nothing about signals, portfolios, or market-data
loaders.  Callers keep their signal payloads keyed by ``order_id`` and pass only
the original price-thesis band plus point-in-time prices into this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Any


POLICY_VERSION = "cash_conflict_unfilled_entry_fifo_persistence_v1"


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must contain an ISO calendar date") from exc


def _positive_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return result


def _nonnegative_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite non-negative number") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return result


@dataclass(frozen=True)
class PendingCashOrder:
    """Unfilled shares from one otherwise-qualified entry order."""

    order_id: str
    ticker: str
    queued_on: date
    requested_shares: int
    initially_admitted_shares: int
    remaining_shares: int
    original_stop_price: float
    original_target_price: float


@dataclass(frozen=True)
class _OrderRegistration:
    """Durable identity used to make enqueue idempotent after completion."""

    order_id: str
    ticker: str
    queued_on: date
    requested_shares: int
    initially_admitted_shares: int
    original_stop_price: float
    original_target_price: float


@dataclass(frozen=True)
class CashConflictQueue:
    """Immutable queue state; tuple order is strict FIFO order."""

    pending: tuple[PendingCashOrder, ...] = ()
    registrations: tuple[_OrderRegistration, ...] = ()


@dataclass(frozen=True)
class QueueDecision:
    """Auditable transition proposed for one queued order."""

    order_id: str
    action: str
    reason: str
    remaining_before: int
    remaining_after: int
    fill_shares: int = 0
    session_date: date | None = None
    fill_price: float | None = None
    cash_used: float = 0.0


def enqueue_unfilled_remainder(
    state: CashConflictQueue,
    *,
    order_id: str,
    ticker: str,
    queued_on: Any,
    requested_shares: int,
    admitted_shares: int,
    original_stop_price: float,
    original_target_price: float,
) -> CashConflictQueue:
    """Append exactly ``requested - admitted`` shares once.

    A repeated registration of the same immutable order is a no-op, including
    after that order has filled or cancelled.  Reusing an ``order_id`` for a
    different order is rejected instead of silently duplicating exposure.
    """

    normalized_id = str(order_id or "").strip()
    normalized_ticker = str(ticker or "").strip().upper()
    if not normalized_id:
        raise ValueError("order_id must be non-empty")
    if not normalized_ticker:
        raise ValueError("ticker must be non-empty")
    if isinstance(requested_shares, bool) or not isinstance(requested_shares, int):
        raise ValueError("requested_shares must be an integer")
    if isinstance(admitted_shares, bool) or not isinstance(admitted_shares, int):
        raise ValueError("admitted_shares must be an integer")
    if requested_shares < 0 or not 0 <= admitted_shares <= requested_shares:
        raise ValueError("shares must satisfy 0 <= admitted <= requested")

    stop = _positive_decimal(original_stop_price, "original_stop_price")
    target = _positive_decimal(original_target_price, "original_target_price")
    if stop >= target:
        raise ValueError("original_stop_price must be below original_target_price")

    registration = _OrderRegistration(
        order_id=normalized_id,
        ticker=normalized_ticker,
        queued_on=_as_date(queued_on, "queued_on"),
        requested_shares=requested_shares,
        initially_admitted_shares=admitted_shares,
        original_stop_price=float(stop),
        original_target_price=float(target),
    )
    for existing in state.registrations:
        if existing.order_id == normalized_id:
            if existing != registration:
                raise ValueError(f"order_id {normalized_id!r} has conflicting fields")
            return state

    remainder = requested_shares - admitted_shares
    pending = state.pending
    if remainder:
        pending = pending + (
            PendingCashOrder(
                **registration.__dict__,
                remaining_shares=remainder,
            ),
        )
    return CashConflictQueue(
        pending=pending,
        registrations=state.registrations + (registration,),
    )


def fifo_head(state: CashConflictQueue) -> PendingCashOrder | None:
    """Return the oldest still-pending order without mutating queue state."""

    return state.pending[0] if state.pending else None


def _decision(
    order: PendingCashOrder,
    action: str,
    reason: str,
    *,
    remaining_after: int | None = None,
    fill_shares: int = 0,
    session_date: date | None = None,
    fill_price: float | None = None,
    cash_used: float = 0.0,
) -> QueueDecision:
    return QueueDecision(
        order_id=order.order_id,
        action=action,
        reason=reason,
        remaining_before=order.remaining_shares,
        remaining_after=(
            order.remaining_shares
            if remaining_after is None
            else remaining_after
        ),
        fill_shares=fill_shares,
        session_date=session_date,
        fill_price=fill_price,
        cash_used=cash_used,
    )


def observe_completed_bar(
    order: PendingCashOrder,
    *,
    as_of: Any,
    bar_date: Any,
    low: float,
    high: float,
) -> QueueDecision:
    """Cancel on a completed post-queue band breach, otherwise keep waiting.

    ``bar_date`` must be strictly earlier than ``as_of``.  This explicit
    contract prevents a caller from using the current session's high/low to
    decide a fill that notionally happened at its open.
    """

    as_of_date = _as_date(as_of, "as_of")
    completed_on = _as_date(bar_date, "bar_date")
    if completed_on >= as_of_date:
        raise ValueError("completed bar must be strictly earlier than as_of")
    bar_low = _positive_decimal(low, "low")
    bar_high = _positive_decimal(high, "high")
    if bar_low > bar_high:
        raise ValueError("low must not exceed high")
    if completed_on < order.queued_on:
        return _decision(order, "wait", "bar_precedes_queue", session_date=as_of_date)

    stop_breached = bar_low <= Decimal(str(order.original_stop_price))
    target_breached = bar_high >= Decimal(str(order.original_target_price))
    if stop_breached or target_breached:
        if stop_breached and target_breached:
            reason = "original_price_band_breached"
        elif stop_breached:
            reason = "original_stop_breached"
        else:
            reason = "original_target_breached"
        return _decision(
            order,
            "cancel",
            reason,
            remaining_after=0,
            session_date=as_of_date,
        )
    return _decision(order, "wait", "original_price_band_intact", session_date=as_of_date)


def evaluate_fifo_head_at_open(
    state: CashConflictQueue,
    *,
    session_date: Any,
    open_price: float,
    available_cash: float,
    eligible: bool = True,
) -> QueueDecision | None:
    """Evaluate only the FIFO head using information known at this open."""

    order = fifo_head(state)
    if order is None:
        return None
    session = _as_date(session_date, "session_date")
    price = _positive_decimal(open_price, "open_price")
    cash = _nonnegative_decimal(available_cash, "available_cash")
    if session < order.queued_on:
        raise ValueError("session_date cannot precede queued_on")
    if session == order.queued_on:
        return _decision(order, "wait", "next_session_not_reached", session_date=session)
    if price <= Decimal(str(order.original_stop_price)):
        return _decision(
            order,
            "cancel",
            "open_at_or_below_original_stop",
            remaining_after=0,
            session_date=session,
            fill_price=float(price),
        )
    if price >= Decimal(str(order.original_target_price)):
        return _decision(
            order,
            "cancel",
            "open_at_or_above_original_target",
            remaining_after=0,
            session_date=session,
            fill_price=float(price),
        )
    if not eligible:
        return _decision(order, "wait", "portfolio_gate_not_eligible", session_date=session)

    affordable = int((cash / price).to_integral_value(rounding=ROUND_FLOOR))
    fill_shares = min(order.remaining_shares, affordable)
    if fill_shares <= 0:
        return _decision(order, "wait", "insufficient_cash", session_date=session)
    remaining = order.remaining_shares - fill_shares
    cash_used = price * fill_shares
    return _decision(
        order,
        "fill",
        "full_fill" if remaining == 0 else "partial_fill",
        remaining_after=remaining,
        fill_shares=fill_shares,
        session_date=session,
        fill_price=float(price),
        cash_used=float(cash_used),
    )


def cancel_fifo_head(
    state: CashConflictQueue,
    *,
    as_of: Any,
    reason: str,
) -> tuple[CashConflictQueue, QueueDecision]:
    """Cancel the FIFO head for a caller-known point-in-time condition.

    This covers portfolio facts outside this helper's scope, such as the
    originally admitted position having exited before its queued top-up filled.
    The caller supplies the reason; no price or future outcome is inspected.
    """

    order = fifo_head(state)
    if order is None:
        raise ValueError("cannot cancel an empty queue")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("reason must be non-empty")
    decision = _decision(
        order,
        "cancel",
        normalized_reason,
        remaining_after=0,
        session_date=_as_date(as_of, "as_of"),
    )
    return apply_queue_decision(state, decision), decision


def apply_queue_decision(
    state: CashConflictQueue,
    decision: QueueDecision,
) -> CashConflictQueue:
    """Apply a decision once, preserving strict FIFO and replay idempotency."""

    order = fifo_head(state)
    if order is None:
        if any(row.order_id == decision.order_id for row in state.registrations):
            return state
        raise ValueError("decision references an unknown order_id")
    if order.order_id != decision.order_id:
        if not any(row.order_id == decision.order_id for row in state.pending):
            # An older, already-applied decision can be replayed harmlessly.
            if any(row.order_id == decision.order_id for row in state.registrations):
                return state
        raise ValueError("decision does not reference the FIFO head")
    if decision.action not in {"wait", "fill", "cancel"}:
        raise ValueError("decision action must be wait, fill, or cancel")
    if order.remaining_shares == decision.remaining_after:
        return state
    if order.remaining_shares < decision.remaining_after:
        # The exact transition was already applied and the order progressed.
        return state
    if order.remaining_shares != decision.remaining_before:
        raise ValueError("decision remaining_before does not match queue state")
    if decision.action == "wait":
        raise ValueError("wait decisions cannot change remaining shares")
    if not 0 <= decision.remaining_after < order.remaining_shares:
        raise ValueError("decision remaining_after is invalid")

    tail = state.pending[1:]
    if decision.remaining_after == 0:
        pending = tail
    else:
        pending = (
            replace(order, remaining_shares=decision.remaining_after),
        ) + tail
    return CashConflictQueue(pending=pending, registrations=state.registrations)
