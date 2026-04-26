import json
import threading
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    append_log_entry,
    build_log_draft,
    claim_ticket,
    create_ticket,
    evaluate_gate,
    experiment_log_exists,
    experiment_id_exists_in_log,
    iter_experiments,
    judge_results,
    locked_registry_update,
    load_registry,
    save_experiment_log_entry,
    save_registry,
    update_result,
)


def test_create_ticket_assigns_incrementing_id_and_baseline(tmp_path):
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_tickets_dir": str(tmp_path / "tickets"),
    }

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
    assert loaded["experiments"][0]["ticket_file"].endswith(
        "tickets/exp-20260426-001.json"
    )


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


def test_claim_ignores_shared_coordination_file_scopes():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    first = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Record one failure taxonomy.",
        change_type="failure_taxonomy",
        single_causal_variable="taxonomy A",
        allowed_write_scope=[
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
    )
    second = create_ticket(
        registry,
        lane="universe_scout",
        hypothesis="Record one universe scout artifact.",
        change_type="universe_expansion",
        single_causal_variable="universe B",
        allowed_write_scope=[
            "D:/Github/ginger/docs/experiment_log.jsonl",
            "D:/Github/ginger/docs/experiment_registry.json",
        ],
    )

    _, conflicts = claim_ticket(registry, first["experiment_id"], "agent-loss")
    assert conflicts == []

    claimed, conflicts = claim_ticket(registry, second["experiment_id"], "agent-universe")
    assert conflicts == []
    assert claimed["status"] == "claimed"


def test_claim_still_blocks_same_locked_variable_with_shared_scopes():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    first = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Study one shared failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="shared failure family",
        allowed_write_scope=["docs/experiment_log.jsonl"],
    )
    second = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Study same shared failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="shared failure family",
        allowed_write_scope=["docs/experiment_registry.json"],
    )

    _, conflicts = claim_ticket(registry, first["experiment_id"], "agent-a")
    assert conflicts == []

    _, conflicts = claim_ticket(registry, second["experiment_id"], "agent-b")
    assert conflicts
    assert conflicts[0]["scope_conflicts"] == []
    assert conflicts[0]["locked_variable_conflicts"] == ["shared failure family"]


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


def test_log_draft_can_be_marked_observed_only_and_appended(tmp_path):
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_tickets_dir": str(tmp_path / "tickets"),
    }
    ticket = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Record a measurement artifact without strategy acceptance.",
        change_type="measurement_instrumentation",
        single_causal_variable="log append path",
        baseline_result_file="data/backtest_results_20260425.json",
        allowed_write_scope=["scripts/"],
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 1.0},
        "delta_metrics": {"expected_value_score": 0.0},
    }

    draft = build_log_draft(
        ticket,
        judgement,
        "data/before.json",
        "data/after.json",
        status_override="observed_only",
        change_summary="Append-log path observed without strategy claim.",
        notes="No strategy decision intended.",
    )
    log_path = tmp_path / "experiment_log.jsonl"
    append_log_entry(log_path, draft)

    assert draft["status"] == "observed_only"
    assert draft["decision"] == "observed_only"
    assert draft["rejection_reason"] is None
    assert experiment_id_exists_in_log(log_path, ticket["experiment_id"])


def test_per_experiment_log_entry_is_written_to_own_file(tmp_path):
    row = {"experiment_id": "exp-20990101-003", "decision": "observed_only"}
    logs_dir = tmp_path / "logs"

    path = save_experiment_log_entry(row, logs_dir=logs_dir)

    assert path == logs_dir / "exp-20990101-003.json"
    assert experiment_log_exists("exp-20990101-003", logs_dir=logs_dir)
    assert json.loads(path.read_text(encoding="utf-8"))["decision"] == "observed_only"


def test_append_log_rejects_duplicate_experiment_id(tmp_path):
    row = {"experiment_id": "exp-20990101-001", "decision": "observed_only"}
    log_path = tmp_path / "experiment_log.jsonl"
    append_log_entry(log_path, row)

    try:
        append_log_entry(log_path, row)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate experiment_id was accepted")


def test_append_log_uses_persistent_lock_file_without_blocking_reuse(tmp_path):
    row = {"experiment_id": "exp-20990101-002", "decision": "observed_only"}
    log_path = tmp_path / "experiment_log.jsonl"
    append_log_entry(log_path, row)
    append_log_entry(
        log_path,
        {"experiment_id": "exp-20990101-003", "decision": "observed_only"},
    )

    assert log_path.exists()
    lock_path = tmp_path / "experiment_log.jsonl.lock"
    assert lock_path.exists()
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock_payload["target"].endswith("experiment_log.jsonl")
    assert "released_at" in lock_payload


def test_locked_registry_update_serializes_read_modify_write(tmp_path):
    registry_path = tmp_path / "experiment_registry.json"
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    def add_ticket(registry):
        return create_ticket(
            registry,
            lane="measurement_repair",
            hypothesis="Create ticket under lock.",
            change_type="logging_fix",
            single_causal_variable="locked registry update",
            baseline_result_file="data/backtest_results_20260425.json",
        )

    ticket = locked_registry_update(registry_path, add_ticket)
    loaded = load_registry(registry_path)

    assert ticket["experiment_id"].endswith("-001")
    assert len(loaded["experiments"]) == 1
    assert iter_experiments(loaded)[0]["single_causal_variable"] == "locked registry update"
    lock_path = tmp_path / "experiment_registry.json.lock"
    assert lock_path.exists()
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock_payload["target"].endswith("experiment_registry.json")
    assert "released_at" in lock_payload


def test_concurrent_locked_registry_updates_do_not_duplicate_ids(tmp_path):
    registry_path = tmp_path / "experiment_registry.json"
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)
    tickets = []

    def worker(i):
        def add_ticket(registry):
            return create_ticket(
                registry,
                lane="measurement_repair",
                hypothesis=f"Create concurrent ticket {i}.",
                change_type="logging_fix",
                single_causal_variable=f"locked registry update {i}",
                baseline_result_file="data/backtest_results_20260425.json",
            )

        tickets.append(locked_registry_update(registry_path, add_ticket))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    loaded = load_registry(registry_path)
    ids = [exp["experiment_id"] for exp in loaded["experiments"]]

    assert len(tickets) == 6
    assert len(ids) == 6
    assert len(set(ids)) == 6
    assert ids == sorted(ids)


def test_update_result_honors_status_override():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Close an analysis ticket as observed only.",
        change_type="analysis_only",
        single_causal_variable="loss taxonomy",
        baseline_result_file="data/backtest_results_20260425.json",
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "delta_metrics": {},
    }

    updated = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "data/before.json",
        "data/after.json",
        status_override="observed_only",
    )

    assert updated["status"] == "observed_only"
    assert updated["result"]["decision"] == "observed_only"
