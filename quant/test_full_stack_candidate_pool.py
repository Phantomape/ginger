"""Unit tests for the full-stack candidate-pool verdict helper.

Covers the execution envelope completeness checklist, the AGENTS.md scout
materiality floor, the Gate-4 composition over evaluate_experiment_promotion_gate,
the codified Gate-5 live-readiness check, and the three-rung verdict ladder
(including the two operator-confirmed decisions: forward-immature Gate-4 pass
lands at accepted_paper_pending_forward, and an incomplete envelope blocks
live_eligible only). Gate 5 also fails closed for missing, incomplete, or
sub-threshold Deflated-Sharpe evidence without changing Gate 4 or paper status.

No JavaScript was used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import deflated_sharpe  # noqa: E402

from quant.full_stack_candidate_pool import (
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    evaluate_materiality,
    full_stack_verdict,
)


def _pass_metrics(**overrides):
    """A window-metrics dict that passes Gate 4 + materiality."""
    base = {
        "aggregate_ev_delta": 0.31,
        "aggregate_pnl_delta": 5000.0,
        "windows_ev_improved": 3,
        "windows_ev_regressed": 0,
        "adjusted_trade_count": 40,
        "adjusted_window_count": 3,
        "max_drawdown_worse_max": 0.001,
        "single_ticker_positive_share": 0.30,
        "baseline_single_ticker_positive_share": 0.32,
        "top_5_contribution_pct": 0.45,
        "baseline_top_5_contribution_pct": 0.50,
        "hhi_concentration": 0.10,
        "baseline_hhi_concentration": 0.12,
        "avg_pnl_per_trade_delta": 600.0,
        "avg_return_delta_pp": 6.0,
    }
    base.update(overrides)
    return base


def _full_envelope():
    return ExecutionEnvelope(
        base_notional=10_000.0,
        max_capital_pct=0.05,
        min_dollar_volume=2_000_000.0,
        slippage_bps=10.0,
        max_displacement=2,
        max_concurrent=5,
        order_semantics="next_open",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.12,
    )


def _dsr_trial(config_id, values, dates):
    rows = [
        {"date": date_label, "return": value}
        for date_label, value in zip(dates, values)
    ]
    return {
        "config_id": config_id,
        "config": {"variant": config_id},
        "attempted": True,
        "selection_scope": "canonical-core-selection-v1",
        "window": {"start": dates[0], "end": dates[-1]},
        "frequency": "daily",
        "return_basis": "strategy_equity_return",
        "risk_free_assumption": "zero",
        "protocol": "canonical-backtest-v1",
        "data": "snapshot-sha256:abc",
        "cost": {"model": "round-trip-v2"},
        "return_series": rows,
        "return_series_sha256": hashlib.sha256(
            json.dumps(
                {"schema": "dated_periodic_return_series_v1", "rows": rows},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "return_series_source": f"data/backtests/{config_id}.json#sharpe_inference",
    }


def _dsr_payload(*, high_probability=True):
    if high_probability:
        dates = [
            (date(2026, 1, 1) + timedelta(days=index)).isoformat()
            for index in range(80)
        ]
        values = [
            [0.012 if index % 2 == 0 else -0.002 for index in range(80)],
            [0.009 if index % 3 else -0.003 for index in range(80)],
            [0.008 if index % 4 in (0, 1) else -0.002 for index in range(80)],
        ]
    else:
        dates = [f"2026-01-{day:02d}" for day in range(2, 8)]
        values = [
            [0.010, -0.004, 0.006, -0.002, 0.008, 0.001],
            [-0.003, 0.009, -0.001, 0.007, -0.004, 0.005],
            [0.006, -0.002, 0.009, -0.005, 0.004, 0.003],
        ]
    trials = [
        _dsr_trial(f"config-{index}", trial_values, dates)
        for index, trial_values in enumerate(values)
    ]
    return {
        "selected_config_id": "config-0",
        "expected_attempt_count": 3,
        "selection_pool_complete": True,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": trials,
    }


def _computed_dsr(**overrides):
    report = deflated_sharpe.build_report(_dsr_payload())
    report["gate5_dsr_report"].update(overrides)
    return report


def _low_dsr_report():
    return deflated_sharpe.build_report(_dsr_payload(high_probability=False))


# --- envelope ---------------------------------------------------------------

def test_envelope_missing_lists_all_required_when_empty():
    env = ExecutionEnvelope()
    missing = env.missing()
    assert "base_notional" in missing
    assert "kill_switch_drawdown_pct" in missing
    assert len(missing) == 9
    assert env.complete() is False


def test_envelope_complete_when_all_required_set():
    env = _full_envelope()
    assert env.missing() == []
    assert env.complete() is True
    d = env.to_dict()
    assert d["complete"] is True and d["missing"] == []


def test_envelope_blank_string_counts_as_missing():
    env = _full_envelope()
    env.order_semantics = "   "
    assert "order_semantics" in env.missing()


# --- materiality ------------------------------------------------------------

def test_materiality_immaterial_only_when_both_below_floor():
    m = evaluate_materiality({"avg_pnl_per_trade_delta": 100.0, "avg_return_delta_pp": 2.0})
    assert m["material"] is False


def test_materiality_material_when_either_above_floor():
    assert evaluate_materiality(
        {"avg_pnl_per_trade_delta": 600.0, "avg_return_delta_pp": 2.0}
    )["material"] is True
    assert evaluate_materiality(
        {"avg_pnl_per_trade_delta": 100.0, "avg_return_delta_pp": 6.0}
    )["material"] is True


def test_materiality_unknown_defaults_material_with_warning():
    m = evaluate_materiality({})
    assert m["material"] is True
    assert "missing_materiality_metrics" in m["warnings"]


# --- gate 4 -----------------------------------------------------------------

def test_gate4_passes_on_clean_metrics():
    g = evaluate_gate4(_pass_metrics())
    assert g["passed"] is True
    assert g["hard_failures"] == []


def test_gate4_fails_on_regressed_window():
    g = evaluate_gate4(_pass_metrics(windows_ev_regressed=1))
    assert g["passed"] is False
    assert "ev_regressed_windows" in g["hard_failures"]


def test_gate4_fails_on_concentration_cap():
    g = evaluate_gate4(_pass_metrics(single_ticker_positive_share=0.65))
    assert g["passed"] is False
    assert any("single_ticker_positive_share" in f for f in g["hard_failures"])


def test_gate4_fails_on_immaterial_effect():
    g = evaluate_gate4(
        _pass_metrics(avg_pnl_per_trade_delta=100.0, avg_return_delta_pp=2.0)
    )
    assert g["passed"] is False
    assert "immaterial_effect" in g["hard_failures"]


# --- gate 5 live readiness --------------------------------------------------

def test_live_readiness_immature_forward_blocks():
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=True,
    )
    assert lr["ready"] is False
    assert any(b.startswith("forward_rows_immature") for b in lr["blockers"])


def test_live_readiness_ready_when_all_satisfied():
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=_computed_dsr(),
    )
    assert lr["ready"] is True
    assert lr["blockers"] == []
    assert lr["dsr_gate"]["passed"] is True
    assert lr["dsr_gate"]["panel_recomputed"] is True


def test_live_readiness_old_call_without_dsr_fails_closed_for_live_only():
    """The old call shape remains valid but cannot silently reach live."""
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
    )
    assert lr["ready"] is False
    assert lr["blockers"] == ["dsr_report_missing"]
    assert lr["dsr_gate"]["reason"] == "dsr_report_missing"


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"status": "pending"}, "status"),
        ({"selection_pool_complete": False}, "selection_pool_complete"),
        ({"panel_hash": "   "}, "panel_hash_recomputation_mismatch"),
        ({"selection_scope_id": ""}, "selection_scope_recomputation_mismatch"),
        ({"dsr_probability": None}, "dsr_probability_recomputation_mismatch"),
    ],
)
def test_live_readiness_blocks_incomplete_dsr_report(overrides, expected_field):
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=_computed_dsr(**overrides),
    )
    assert lr["ready"] is False
    assert lr["blockers"] == ["dsr_report_incomplete"]
    assert lr["dsr_gate"]["reason"] == "dsr_report_incomplete"
    assert expected_field in lr["dsr_gate"]["incomplete_fields"]


@pytest.mark.parametrize("invalid_probability", [True, float("nan"), -0.01, 1.01])
def test_live_readiness_treats_invalid_dsr_probability_as_incomplete(
    invalid_probability,
):
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=_computed_dsr(dsr_probability=invalid_probability),
    )
    assert lr["ready"] is False
    assert lr["dsr_gate"]["reason"] == "dsr_report_incomplete"
    assert "dsr_probability_recomputation_mismatch" in lr["dsr_gate"]["incomplete_fields"]


def test_live_readiness_blocks_complete_dsr_below_probability_threshold():
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=_low_dsr_report(),
    )
    assert lr["ready"] is False
    assert lr["blockers"] == ["dsr_probability_below_threshold"]
    assert lr["dsr_gate"]["reason"] == "dsr_probability_below_threshold"
    assert lr["dsr_gate"]["required_probability"] == 0.95


def test_live_readiness_rejects_five_field_summary_without_recomputable_panel():
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report={
            "status": "computed",
            "selection_pool_complete": True,
            "panel_hash": "x",
            "selection_scope_id": "x",
            "dsr_probability": 0.99,
        },
    )
    assert lr["ready"] is False
    assert lr["dsr_gate"]["reason"] == "dsr_report_incomplete"
    assert "panel_input" in lr["dsr_gate"]["incomplete_fields"]


def test_live_readiness_rejects_panel_tampering_after_report_generation():
    report = _computed_dsr()
    report["panel_input"]["trials"][0]["return_series"][0]["return"] += 0.5
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=report,
    )
    assert lr["ready"] is False
    assert lr["dsr_gate"]["reason"] == "dsr_report_incomplete"
    assert "panel_recomputation" in lr["dsr_gate"]["incomplete_fields"]
    assert any(
        "return_series_hash_mismatch" in reason
        for reason in lr["dsr_gate"]["recomputation_reason_codes"]
    )


def test_live_readiness_rejects_tampered_nested_panel_result():
    report = _computed_dsr()
    report["panel_result"]["panel_sha256"] = "0" * 64
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=report,
    )
    assert lr["ready"] is False
    assert lr["dsr_gate"]["reason"] == "dsr_report_incomplete"
    assert "panel_result_hash_recomputation_mismatch" in lr["dsr_gate"][
        "incomplete_fields"
    ]


# --- verdict ladder ---------------------------------------------------------

def test_verdict_reject_when_gate4_fails():
    g = evaluate_gate4(_pass_metrics(windows_ev_regressed=1))
    lr = evaluate_live_readiness(envelope=_full_envelope(), closed_forward_trades=0)
    v = full_stack_verdict(gate4=g, live_readiness=lr, envelope=_full_envelope())
    assert v["verdict"] == "reject"


def test_verdict_accepted_paper_pending_forward_when_gate4_passes_but_immature():
    # Decision 1: a first one-shot Gate-4 pass with immature forward rows is an
    # accepted paper sleeve, not a mere lead.
    g = evaluate_gate4(_pass_metrics())
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=True,
    )
    v = full_stack_verdict(gate4=g, live_readiness=lr, envelope=_full_envelope())
    assert v["verdict"] == "accepted_paper_pending_forward"
    assert "no new experiment is needed" in v["next_step"].lower()


def test_verdict_live_eligible_when_gate4_and_gate5_pass():
    g = evaluate_gate4(_pass_metrics())
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=_computed_dsr(),
    )
    v = full_stack_verdict(gate4=g, live_readiness=lr, envelope=_full_envelope())
    assert v["verdict"] == "live_eligible"


def test_incomplete_envelope_blocks_live_only():
    # Decision 2: an incomplete envelope blocks live_eligible but NOT
    # accepted_paper_pending_forward.
    env = _full_envelope()
    env.slippage_bps = None  # incomplete
    g = evaluate_gate4(_pass_metrics())
    lr = evaluate_live_readiness(
        envelope=env,
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
        dsr_report=_computed_dsr(),
    )
    assert lr["ready"] is False
    assert "execution_envelope_incomplete" in lr["blockers"]
    v = full_stack_verdict(gate4=g, live_readiness=lr, envelope=env)
    assert v["verdict"] == "accepted_paper_pending_forward"


def test_missing_dsr_blocks_live_but_preserves_gate4_and_paper_acceptance():
    g = evaluate_gate4(_pass_metrics())
    lr = evaluate_live_readiness(
        envelope=_full_envelope(),
        closed_forward_trades=35,
        forward_pnl=4200.0,
        replacement_value_passed=True,
        kill_switch_parity_passed=True,
    )
    v = full_stack_verdict(gate4=g, live_readiness=lr, envelope=_full_envelope())
    assert g["passed"] is True
    assert v["gate4_passed"] is True
    assert v["verdict"] == "accepted_paper_pending_forward"
    assert v["live_readiness"]["blockers"] == ["dsr_report_missing"]
