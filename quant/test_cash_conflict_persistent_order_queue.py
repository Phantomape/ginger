from datetime import date

import pytest

from cash_conflict_persistent_order_queue import (
    CashConflictQueue,
    QueueDecision,
    apply_queue_decision,
    cancel_fifo_head,
    enqueue_unfilled_remainder,
    evaluate_fifo_head_at_open,
    fifo_head,
    observe_completed_bar,
)


def _enqueue(
    state: CashConflictQueue,
    order_id: str = "2026-01-02:AAA:0",
    ticker: str = "AAA",
    requested: int = 10,
    admitted: int = 4,
) -> CashConflictQueue:
    return enqueue_unfilled_remainder(
        state,
        order_id=order_id,
        ticker=ticker,
        queued_on="2026-01-02",
        requested_shares=requested,
        admitted_shares=admitted,
        original_stop_price=90.0,
        original_target_price=120.0,
    )


def test_enqueue_keeps_exact_remainder_and_is_idempotent():
    state = _enqueue(CashConflictQueue())
    assert fifo_head(state).remaining_shares == 6
    assert _enqueue(state) is state

    zero_remainder = _enqueue(
        CashConflictQueue(), order_id="done", requested=10, admitted=10
    )
    assert zero_remainder.pending == ()
    assert _enqueue(
        zero_remainder, order_id="done", requested=10, admitted=10
    ) is zero_remainder


def test_reused_order_id_with_different_payload_is_rejected():
    state = _enqueue(CashConflictQueue())
    with pytest.raises(ValueError, match="conflicting fields"):
        _enqueue(state, ticker="BBB")


def test_fifo_order_and_partial_then_full_fill_are_exact():
    state = _enqueue(CashConflictQueue(), order_id="first", requested=10, admitted=2)
    state = _enqueue(state, order_id="second", ticker="BBB", requested=5, admitted=0)
    assert [row.order_id for row in state.pending] == ["first", "second"]

    partial = evaluate_fifo_head_at_open(
        state,
        session_date="2026-01-05",
        open_price=100.0,
        available_cash=350.0,
    )
    assert (partial.action, partial.fill_shares, partial.remaining_after) == (
        "fill",
        3,
        5,
    )
    assert partial.cash_used == 300.0
    state = apply_queue_decision(state, partial)
    assert fifo_head(state).remaining_shares == 5
    assert apply_queue_decision(state, partial) is state

    full = evaluate_fifo_head_at_open(
        state,
        session_date=date(2026, 1, 6),
        open_price=100.0,
        available_cash=500.0,
    )
    state = apply_queue_decision(state, full)
    assert fifo_head(state).order_id == "second"


def test_same_session_and_cash_or_portfolio_constraints_wait():
    state = _enqueue(CashConflictQueue())
    same_day = evaluate_fifo_head_at_open(
        state,
        session_date="2026-01-02",
        open_price=100.0,
        available_cash=1000.0,
    )
    no_cash = evaluate_fifo_head_at_open(
        state,
        session_date="2026-01-05",
        open_price=100.0,
        available_cash=99.99,
    )
    ineligible = evaluate_fifo_head_at_open(
        state,
        session_date="2026-01-05",
        open_price=100.0,
        available_cash=1000.0,
        eligible=False,
    )
    assert same_day.reason == "next_session_not_reached"
    assert no_cash.reason == "insufficient_cash"
    assert ineligible.reason == "portfolio_gate_not_eligible"


@pytest.mark.parametrize(
    ("low", "high", "reason"),
    [
        (89.0, 110.0, "original_stop_breached"),
        (95.0, 121.0, "original_target_breached"),
        (89.0, 121.0, "original_price_band_breached"),
    ],
)
def test_only_completed_past_bars_can_cancel(low, high, reason):
    state = _enqueue(CashConflictQueue())
    order = fifo_head(state)
    decision = observe_completed_bar(
        order,
        as_of="2026-01-05",
        bar_date="2026-01-02",
        low=low,
        high=high,
    )
    assert (decision.action, decision.reason) == ("cancel", reason)
    state = apply_queue_decision(state, decision)
    assert state.pending == ()
    assert apply_queue_decision(state, decision) is state

    with pytest.raises(ValueError, match="strictly earlier"):
        observe_completed_bar(
            order,
            as_of="2026-01-05",
            bar_date="2026-01-05",
            low=95.0,
            high=110.0,
        )


@pytest.mark.parametrize(
    ("price", "reason"),
    [
        (90.0, "open_at_or_below_original_stop"),
        (120.0, "open_at_or_above_original_target"),
    ],
)
def test_current_open_can_cancel_without_current_session_high_low(price, reason):
    state = _enqueue(CashConflictQueue())
    decision = evaluate_fifo_head_at_open(
        state,
        session_date="2026-01-05",
        open_price=price,
        available_cash=1000.0,
    )
    assert (decision.action, decision.reason, decision.remaining_after) == (
        "cancel",
        reason,
        0,
    )


def test_non_head_decision_is_rejected():
    state = _enqueue(CashConflictQueue(), order_id="first")
    state = _enqueue(state, order_id="second", ticker="BBB")
    decision = QueueDecision(
        order_id="second",
        action="cancel",
        reason="test",
        remaining_before=6,
        remaining_after=0,
    )
    with pytest.raises(ValueError, match="FIFO head"):
        apply_queue_decision(state, decision)


def test_caller_can_cancel_head_after_original_position_exits():
    state = _enqueue(CashConflictQueue(), requested=10, admitted=4)
    state, decision = cancel_fifo_head(
        state,
        as_of="2026-01-06",
        reason="original_position_closed",
    )
    assert state.pending == ()
    assert (decision.action, decision.reason, decision.remaining_before) == (
        "cancel",
        "original_position_closed",
        6,
    )
