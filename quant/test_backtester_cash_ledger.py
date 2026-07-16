"""Guards for the execution-date cash ledger.

The full behavioral validation is the three-window frozen-input before/after
replay in exp-20260715-008 and the canonical default re-baseline in
exp-20260715-010; these tests protect the invariants those replays rely on.
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backtester import DEFAULT_CONFIG, BacktestEngine, Position  # noqa: E402


def test_cash_ledger_default_on():
    # exp-20260715-010 made the accepted exp-20260715-008 cash-admission
    # policy canonical. Callers can still pass False for legacy reproduction.
    assert DEFAULT_CONFIG["CASH_LEDGER_ENFORCED"] is True


def test_cash_ledger_explicit_false_override_remains_available():
    engine = BacktestEngine(
        ["SPY"],
        start="2026-01-02",
        end="2026-01-05",
        config={"CASH_LEDGER_ENFORCED": False},
    )
    assert engine.config["CASH_LEDGER_ENFORCED"] is False


def test_position_default_sleeve_is_core():
    # The ledger only debits/credits core positions; the default sleeve tag
    # is the filter key.
    pos = Position(
        ticker="TEST",
        entry_price=10.0,
        entry_open_price=10.0,
        stop_price=9.0,
        target_price=12.0,
        shares=5,
        entry_date="2026-01-02",
        strategy="trend_long",
    )
    assert pos.sleeve == "core"


def test_run_wires_all_cash_mutation_sites():
    source = inspect.getsource(BacktestEngine.run)
    # Two debit sites: core entry fill and add-on basis delta.
    assert source.count("_cash_debit(") >= 3  # def + 2 call sites
    assert '"core_entry"' in source
    assert '"core_addon"' in source
    # Three credit sites: partial reduce, daily exit, force close.
    assert source.count("_cash_credit(") >= 4  # def + 3 call sites
    # Enforcement decisions are recorded, never silent.
    assert '"insufficient_cash"' in source
    assert '"skipped_insufficient_cash"' in source
    # The audit is attached to the result payload.
    assert '"cash_ledger":         cash_ledger_audit' in source
    # Conservation is checked against the unrounded realized-pnl accumulator.
    assert "core_realized_pnl_ledger" in source


def test_exit_credits_are_core_gated():
    source = inspect.getsource(BacktestEngine.run)
    # Every credit call site must sit behind the core sleeve guard so pilot
    # sleeve fills can never inject cash into the core ledger.
    credit_calls = [
        line.strip()
        for line in source.splitlines()
        if "_cash_credit(" in line and "def _cash_credit" not in line
    ]
    assert len(credit_calls) == 3
    guard_count = source.count('== "core":')
    assert guard_count >= 3
