from copy import deepcopy

from paper_sleeve_execution_contract import (
    RULE_VERSION,
    apply_execution_sizing_contract,
    apply_execution_sizing_contracts,
)


def _complete_envelope() -> dict[str, object]:
    return {
        "max_position_notional_usd": 2_500.0,
        "max_capital_pct": 0.025,
        "min_dollar_volume": 20_000_000.0,
        "slippage_bps": 20.0,
        "max_displacement": "no_core_displacement",
        "max_concurrent_positions": 1,
        "order_semantics": "next_session_open_limit",
        "kill_switch_drawdown_pct": 0.08,
        "failure_policy": "skip_without_retry",
    }


def test_undeclared_execution_envelope_is_fail_closed_without_changing_paper_evidence():
    snapshot = {
        "sleeve": "EXAMPLE_PAPER",
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": 1,
        "candidates": [{"ticker": "COIN", "notional": 10_000.0}],
        "pending_count": 1,
        "pending_entries": [{"ticker": "COIN", "paper_notional_usd": 10_000.0}],
        "realized_pnl_to_date": 1_888.56,
        "unrealized_pnl": 136.01,
    }
    before = deepcopy(snapshot)

    contract = apply_execution_sizing_contract(snapshot, surface_name="example")

    assert contract["rule_version"] == RULE_VERSION
    assert contract["status"] == "blocked"
    assert "execution_envelope_undeclared" in contract["blockers"]
    assert "trade_adapter_disabled" in contract["blockers"]
    assert snapshot["pending_entries"][0]["paper_notional_usd"] == 10_000.0
    assert snapshot["pending_entries"][0]["experiment_notional_usd"] is None
    assert snapshot["realized_pnl_to_date"] == before["realized_pnl_to_date"]
    assert snapshot["unrealized_pnl"] == before["unrealized_pnl"]
    assert snapshot["candidate_count"] == before["candidate_count"]


def test_complete_envelope_caps_explicitly_enabled_experiment_notional():
    snapshot = {
        "sleeve": "EXAMPLE_PAPER",
        "paper_enabled": True,
        "trade_enabled": True,
        "forward_paper_gate": {"passed": True, "status": "passed"},
        "execution_envelope": _complete_envelope(),
        "pending_count": 1,
        "pending_entries": [{"ticker": "COIN", "paper_notional_usd": 10_000.0}],
    }

    contract = apply_execution_sizing_contract(snapshot, surface_name="example")

    assert contract["status"] == "ready"
    assert contract["execution_envelope"]["complete"] is True
    assert snapshot["pending_entries"][0]["paper_notional_usd"] == 10_000.0
    assert snapshot["pending_entries"][0]["experiment_notional_usd"] == 2_500.0
    assert snapshot["pending_entries"][0]["execution_sizing_status"] == "ready"


def test_zero_position_cap_is_incomplete_and_never_falls_back_to_paper_notional():
    envelope = _complete_envelope()
    envelope["max_position_notional_usd"] = 0
    snapshot = {
        "paper_enabled": True,
        "trade_enabled": True,
        "forward_paper_gate": {"passed": True},
        "execution_envelope": envelope,
        "pending_count": 1,
        "pending_entries": [{"ticker": "COIN", "paper_notional_usd": 10_000.0}],
    }

    contract = apply_execution_sizing_contract(snapshot, surface_name="invalid")

    assert contract["execution_envelope"]["complete"] is False
    assert "max_position_notional_usd" in contract["execution_envelope"]["missing_fields"]
    assert snapshot["pending_entries"][0]["experiment_notional_usd"] is None
    assert "execution_envelope_incomplete" in snapshot["pending_entries"][0][
        "execution_sizing_blockers"
    ]


def test_aggregate_contract_reports_all_surfaces_and_pending_blockers():
    surfaces = {
        "one": {
            "sleeve": "ONE",
            "paper_enabled": True,
            "trade_enabled": False,
            "pending_count": 1,
            "pending_entries": [{"ticker": "AAA", "paper_notional_usd": 4_000.0}],
        },
        "two": {
            "sleeve": "TWO",
            "paper_enabled": True,
            "trade_enabled": False,
            "pending_count": 0,
            "pending_entries": [],
        },
    }

    summary = apply_execution_sizing_contracts(surfaces)

    assert summary["surface_count"] == 2
    assert summary["pending_action_count"] == 1
    assert summary["blocked_pending_action_count"] == 1
    assert summary["executable_pending_action_count"] == 0
    assert summary["pending_actions"][0]["paper_notional_usd"] == 4_000.0
    assert summary["pending_actions"][0]["experiment_notional_usd"] is None
    assert summary["production_impact"]["alters_orders"] is False


def test_new_pending_only_surface_is_included_once_in_pending_summary():
    pending = {
        "decision_id": "one",
        "ticker": "MU",
        "paper_notional_usd": 1_600.0,
    }
    summary = apply_execution_sizing_contracts(
        {
            "supplier": {
                "paper_enabled": True,
                "trade_enabled": False,
                "pending_count": 1,
                "pending_entries": [deepcopy(pending)],
                "new_pending_entries": [deepcopy(pending)],
            },
            "industry": {
                "paper_enabled": True,
                "trade_enabled": False,
                "pending_count": 1,
                "new_pending_entries": [
                    {
                        "decision_id": "two",
                        "ticker": "LITE",
                        "paper_notional_usd": 4_000.0,
                    }
                ],
            },
        }
    )

    assert summary["pending_action_count"] == 2
    assert {row["ticker"] for row in summary["pending_actions"]} == {"MU", "LITE"}


def test_pending_count_without_rows_is_reported_as_unresolved_and_blocked():
    summary = apply_execution_sizing_contracts(
        {
            "legacy": {
                "paper_enabled": True,
                "trade_enabled": False,
                "pending_count": 2,
            }
        }
    )

    assert summary["pending_action_count"] == 2
    assert summary["observed_pending_action_count"] == 0
    assert summary["unresolved_pending_action_count"] == 2
    assert summary["blocked_pending_action_count"] == 2
    assert "pending_action_rows_unavailable" in summary["surfaces"][0]["blockers"]


def test_report_labels_paper_notional_as_evidence_and_experiment_as_blocked():
    from report_generator import generate_daily_report

    summary = apply_execution_sizing_contracts(
        {
            "sec_leadership_event_sleeve": {
                "sleeve": "SEC_LEADERSHIP_EVENT_SLEEVE_PAPER",
                "paper_enabled": True,
                "trade_enabled": False,
                "pending_count": 1,
                "pending_entries": [
                    {"ticker": "COIN", "paper_notional_usd": 10_000.0}
                ],
            }
        }
    )

    report = generate_daily_report(
        signals=[],
        paper_sleeve_execution_contract=summary,
    )

    assert "PAPER SLEEVE EXECUTION SIZING" in report
    assert "COIN [sec_leadership_event_sleeve]" in report
    assert "paper=$10,000.00 evidence only" in report
    assert "experiment=BLOCKED" in report
