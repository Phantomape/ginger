from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260525_021_expectation_residual_readiness_audit import (  # noqa: E402
    BUCKET_A,
    build_readiness_summary,
    production_impact,
)


def _row(**overrides):
    row = {
        "as_of_date": "2026-05-07",
        "ticker": "ACME",
        "candidate_source": "signals",
        "record_type": "selected_signal",
        "selected_signal": True,
        "strategy": "breakout_long",
        "expectation_positive": False,
        "expectation_join_status": "missing_ledger_row",
        "expectation_coverage_gap": "missing_ledger_row",
        "ledger_joined": False,
        "ledger_usable": False,
        "eps_estimate_delta_7d": None,
        "eps_estimate_delta_30d": None,
        "residual_leader": False,
        "residual_context_status": "missing_feature_row",
        "residual_state": None,
        "residual_strength_score": None,
        "forward_outcomes": {
            "5d": {"closed": True, "gap_reason": None},
            "10d": {"closed": True, "gap_reason": None},
            "20d": {"closed": False, "gap_reason": "missing_20d_forward_price"},
        },
    }
    row.update(overrides)
    return row


def test_positive_expectation_residual_leader_enters_bucket_a():
    summary = build_readiness_summary(
        [
            _row(
                expectation_positive=True,
                expectation_join_status="usable_ledger_with_7d_delta",
                expectation_coverage_gap=None,
                ledger_joined=True,
                ledger_usable=True,
                eps_estimate_delta_7d=0.12,
                eps_estimate_delta_30d=0.20,
                residual_leader=True,
                residual_context_status="ok",
                residual_state="strong_residual_leader",
                residual_strength_score=0.25,
            )
        ]
    )

    assert summary["bucket_counts"][BUCKET_A] == 1
    bucket_a = summary["bucket_readiness"][BUCKET_A]
    assert bucket_a["candidate_count"] == 1
    assert bucket_a["forward_close_availability"]["5d"]["closed"] == 1
    assert bucket_a["bucket_a_readiness_blocking_reason_counts"] == {}
    assert summary["candidate_readiness_rows"][0]["bucket_a_5d_ready"] is True


def test_usable_ledger_missing_7d_delta_is_not_positive_expectation():
    summary = build_readiness_summary(
        [
            _row(
                expectation_positive=False,
                expectation_join_status="usable_ledger_missing_7d_delta",
                expectation_coverage_gap="missing_eps_estimate_delta_7d",
                ledger_joined=True,
                ledger_usable=True,
                eps_estimate_delta_7d=None,
                residual_leader=True,
                residual_context_status="ok",
                residual_state="residual_leader",
                residual_strength_score=0.08,
            )
        ]
    )

    assert summary["bucket_counts"][BUCKET_A] == 0
    assert summary["bucket_counts"]["C_residual_leader_only"] == 1
    assert summary["bucket_a_readiness_blocking_reason_counts"] == {
        "expectation:missing_eps_estimate_delta_7d": 1
    }
    assert summary["candidate_readiness_rows"][0]["bucket_a_5d_ready"] is False


def test_residual_input_gap_is_explicit_blocking_reason():
    summary = build_readiness_summary(
        [
            _row(
                expectation_positive=True,
                expectation_join_status="usable_ledger_with_7d_delta",
                expectation_coverage_gap=None,
                ledger_joined=True,
                ledger_usable=True,
                eps_estimate_delta_7d=0.05,
                residual_leader=False,
                residual_context_status="insufficient_residual_inputs",
            )
        ]
    )

    assert summary["bucket_counts"][BUCKET_A] == 0
    assert summary["bucket_counts"]["B_positive_expectation_only"] == 1
    assert summary["bucket_a_readiness_blocking_reason_counts"] == {
        "residual:insufficient_residual_inputs": 1
    }


def test_readiness_audit_production_impact_contract_is_all_false():
    impact = production_impact()

    assert impact
    assert all(value is False for value in impact.values())
