import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    claim_ticket,
    create_ticket,
    evaluate_gate,
    judge_results,
    load_registry,
    save_registry,
)


def test_create_ticket_assigns_incrementing_id_and_baseline(tmp_path):
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    first = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Find repeated bad trade family.",
        change_type="analysis_only",
        single_causal_variable="bad trade taxonomy",
        baseline_result_file="data/backtest_results_20260425.json",
        allowed_write_scope=["docs/"],
        evaluation_windows=[{"start": "2025-10-23", "end": "2026-04-21"}],
    )
    second = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Make replay coverage measurable.",
        change_type="measurement_instrumentation",
        single_causal_variable="replay coverage bucket",
        baseline_result_file="data/backtest_results_20260425.json",
        allowed_write_scope=["scripts/"],
    )

    assert first["experiment_id"].endswith("-001")
    assert second["experiment_id"].endswith("-002")
    assert first["status"] == "proposed"
    assert first["baseline_result_file"] == "data/backtest_results_20260425.json"

    path = tmp_path / "registry.json"
    save_registry(registry, path)
    loaded = load_registry(path)
    assert len(loaded["experiments"]) == 2


def test_claim_detects_scope_and_variable_conflicts():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    first = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test one breakout ranking key.",
        change_type="ranking_rule",
        single_causal_variable="breakout ranking key",
        allowed_write_scope=["quant/signal_engine.py"],
    )
    second = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test conflicting breakout ranking key.",
        change_type="ranking_rule",
        single_causal_variable="breakout ranking key",
        allowed_write_scope=["quant/"],
    )

    claimed, conflicts = claim_ticket(registry, first["experiment_id"], "agent-a")
    assert claimed["status"] == "claimed"
    assert conflicts == []

    _, conflicts = claim_ticket(registry, second["experiment_id"], "agent-b")
    assert conflicts
    assert conflicts[0]["experiment_id"] == first["experiment_id"]
    assert conflicts[0]["locked_variable_conflicts"] == ["breakout ranking key"]


def test_evaluate_gate_accepts_expected_value_improvement():
    before = {
        "expected_value_score": 1.0,
        "sharpe": 2.0,
        "max_drawdown_pct": 0.05,
        "win_rate": 0.5,
        "trade_count": 20,
        "total_pnl": 1000.0,
    }
    after = {
        "expected_value_score": 1.11,
        "sharpe": 2.0,
        "max_drawdown_pct": 0.05,
        "win_rate": 0.5,
        "trade_count": 20,
        "total_pnl": 1000.0,
    }

    judgement = evaluate_gate(before, after)

    assert judgement["decision"] == "accepted"
    assert "expected_value_score improved" in judgement["acceptance_reasons"][0]


def test_judge_results_extracts_metrics_and_rejects_no_delta(tmp_path):
    before = {
        "total_trades": 10,
        "win_rate": 0.5,
        "total_pnl": 1000.0,
        "sharpe": 1.0,
        "sharpe_daily": 1.5,
        "max_drawdown_pct": 0.04,
        "survival_rate": 0.9,
        "benchmarks": {"strategy_total_return_pct": 0.1},
    }
    after = dict(before)
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_path.write_text(json.dumps(before), encoding="utf-8")
    after_path.write_text(json.dumps(after), encoding="utf-8")

    judgement = judge_results(before_path, after_path)

    assert judgement["before_metrics"]["expected_value_score"] == 0.15
    assert judgement["delta_metrics"]["trade_count"] == 0
    assert judgement["decision"] == "rejected"
