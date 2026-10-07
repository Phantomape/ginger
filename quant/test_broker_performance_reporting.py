"""Broker measurements must remain distinct from paper gates and trade advice."""

import ast
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from report_generator import generate_daily_report


def _summary(net=117.0):
    return {
        "status": "partial",
        "source_as_of": "2026-09-01T20:00:00Z",
        "counts": {
            "evaluated_lifecycle_count": 2,
            "excluded_lifecycle_count": 1,
            "unlinked_fill_count": 3,
        },
        "pnl_by_currency": {"USD": {
            "gross_trading_pnl_before_order_fees": 120.0,
            "order_fee_total": 3.0,
            "net_trading_pnl_after_order_fees": net,
        }},
        "coverage_reasons": {"missing_fee": 1},
        "trade_enabled": False,
    }


def test_paper_gate_cannot_replace_diary_or_broker_performance():
    diary = {
        "total_trades": 7, "win_rate": 0.5, "avg_win_usd": 50.0,
        "avg_loss_usd": -20.0, "expected_value_usd": 15.0,
        "max_drawdown_usd": 30.0, "total_pnl_usd": 321.0,
    }
    paper = {
        "candidate_count": 1,
        "forward_paper_gate": {"status": "blocked", "metrics": {
            "closed_trades": 99, "win_rate": 0.99,
        }},
    }
    broker = _summary()
    original = deepcopy((diary, paper, broker))
    report = generate_daily_report(
        [], metrics=diary, state_surface_sleeve=paper,
        broker_performance=broker,
    )
    assert "Closed trades:   7" in report
    assert "Total P&L:       $321.00" in report
    assert "Net trading P&L after order fees: $117.00" in report
    assert "strategy attribution unavailable" in report
    assert (diary, paper, broker) == original


def test_missing_broker_measurement_is_not_reported_as_zero_profit():
    report = generate_daily_report([], broker_performance=_summary(None))
    assert "Net trading P&L: unavailable (not zero)" in report
    assert "Net trading P&L after order fees: $0.00" not in report
    assert "missing_fee=1" in report


def test_daily_report_and_json_receive_same_measurement_without_changing_signals():
    # Execute the actual output statements, excluding network/strategy work.
    tree = ast.parse(Path(__file__).with_name("run.py").read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    output_nodes = [node for node in main.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id in {
                        "execution_attribution", "broker_performance", "report", "quant_signals_payload",
                    } for target in node.targets)]
    loads = {node.id for statement in output_nodes for node in ast.walk(statement)
             if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    scope = dict.fromkeys(loads)
    summary = _summary()
    attribution = {"status": "ok", "decisions": [], "trade_enabled": False}
    signals = [{"ticker": "TEST", "strategy": "fixture", "action": "WAIT", "risk": 0}]
    scope.update({
        "_build_broker_performance_snapshot": lambda: summary,
        "_build_execution_attribution_snapshot": lambda **kwargs: attribution,
        "generate_daily_report": generate_daily_report,
        "signals": signals, "entry_cash_admission": {"observations": []},
        "datetime": datetime, "timezone": timezone,
    })
    frozen_signals = deepcopy(signals)
    exec(compile(ast.Module(body=output_nodes, type_ignores=[]), "daily_outputs", "exec"), scope)
    assert scope["quant_signals_payload"]["broker_performance"] is summary
    assert scope["quant_signals_payload"]["execution_attribution"] is attribution
    assert scope["quant_signals_payload"]["signals"] is signals
    assert signals == frozen_signals
    assert "Net trading P&L after order fees: $117.00" in scope["report"]


def test_measurement_failure_stays_visible_and_does_not_raise(monkeypatch):
    import broker_performance
    from run import _build_broker_performance_snapshot

    def fail():
        raise OSError("temporary read failure")

    monkeypatch.setattr(broker_performance, "compute_broker_performance", fail)
    summary = _build_broker_performance_snapshot()
    assert summary["status"] == "unavailable"
    assert summary["trade_enabled"] is False
    assert summary["pnl_by_currency"]["USD"]["net_trading_pnl_after_order_fees"] is None


def test_explicit_subset_is_distinct_from_account_sample_and_order_authorization():
    summary = _summary()
    summary["strategy_attribution"] = {"unattributed_lifecycle_count": 3,
        "by_strategy": {"core:fixture": {"evaluated_lifecycle_count": 1,
                                        "net_trading_pnl_after_order_fees": 95}}}
    advice = {"status": "ok", "decisions": [{"broker_remark": "GNG-" + "a" * 28,
        "decision": {"code": "US.AAPL", "side": "BUY", "quantity": 10,
                     "action_kind": "entry", "strategy_id": "core:fixture"}}]}
    before = deepcopy((summary, advice))
    report = generate_daily_report([], broker_performance=summary, execution_attribution=advice)
    assert "Net trading P&L after order fees: $117.00" in report
    assert "core:fixture: 1 closed; net after order fees $95.00" in report
    assert "Unattributed closed lifecycles: 3" in report
    assert "no orders submitted" in report
    assert "remark=GNG-" + "a" * 28 in report
    assert (summary, advice) == before


def test_attribution_snapshot_failure_does_not_fail_advice_pipeline(monkeypatch):
    import execution_attribution
    from run import _build_execution_attribution_snapshot

    def fail(**kwargs):
        raise ValueError("missing broker refresh")

    monkeypatch.setattr(execution_attribution, "build_daily_attribution_decisions", fail)
    result = _build_execution_attribution_snapshot()
    assert result == {"status": "unavailable", "decisions": [], "trade_enabled": False,
                      "stage": "machine_advice_not_order_authorization"}
