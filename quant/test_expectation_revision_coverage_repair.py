from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260525_023_expectation_revision_coverage_repair import (  # noqa: E402
    delta_gap_reason,
    expectation_state,
    ledger_gap_reason,
    production_impact,
)


def test_missing_ledger_and_missing_snapshot_has_explicit_root_cause():
    reason = ledger_gap_reason(
        as_of="2026-05-07",
        ticker="ACME",
        ledger_row=None,
        ledger_file_exists=False,
        snapshot_info=None,
    )

    assert reason == "missing_ledger_file_and_same_day_earnings_snapshot"


def test_snapshot_exists_but_ticker_missing_has_explicit_root_cause():
    reason = ledger_gap_reason(
        as_of="2026-05-07",
        ticker="ACME",
        ledger_row=None,
        ledger_file_exists=True,
        snapshot_info={"tickers": {"OTHER"}, "ticker_count": 1},
    )

    assert reason == "ticker_missing_from_earnings_snapshot"


def test_usable_ledger_missing_7d_delta_explains_short_same_event_history():
    row = {
        "as_of_date": "2026-05-07",
        "ticker": "ACME",
        "estimate_revision_usable": True,
        "prior_snapshot_date": "2026-05-04",
        "eps_estimate_delta_7d": None,
    }

    assert delta_gap_reason(row, "eps_estimate_delta_7d") == (
        "same_event_history_too_short_for_7d_delta"
    )
    assert expectation_state(row) == "usable_ledger_missing_7d_delta"


def test_non_usable_ledger_missing_delta_carries_pit_caveat():
    row = {
        "as_of_date": "2026-05-07",
        "ticker": "ACME",
        "estimate_revision_usable": False,
        "pit_caveat": "no_prior_same_event_snapshot",
        "eps_estimate_delta_7d": None,
    }

    assert delta_gap_reason(row, "eps_estimate_delta_7d") == (
        "ledger_row_not_usable:no_prior_same_event_snapshot"
    )
    assert expectation_state(row) == "ledger_row_not_usable"


def test_non_usable_ledger_delta_value_still_carries_pit_caveat():
    row = {
        "as_of_date": "2026-05-07",
        "ticker": "ACME",
        "estimate_revision_usable": False,
        "pit_caveat": "prior_snapshot_created_after_asof",
        "eps_estimate_delta_7d": 0.0,
    }

    assert delta_gap_reason(row, "eps_estimate_delta_7d") == (
        "ledger_row_not_usable:prior_snapshot_created_after_asof"
    )
    assert expectation_state(row) == "ledger_row_not_usable"


def test_positive_expectation_requires_usable_positive_7d_delta():
    assert expectation_state(
        {"estimate_revision_usable": True, "eps_estimate_delta_7d": 0.01}
    ) == "positive_expectation_ready"
    assert expectation_state(
        {"estimate_revision_usable": True, "eps_estimate_delta_7d": 0.0}
    ) == "non_positive_eps_estimate_delta_7d"


def test_coverage_repair_production_impact_contract_is_all_false():
    impact = production_impact()

    assert impact
    assert all(value is False for value in impact.values())
