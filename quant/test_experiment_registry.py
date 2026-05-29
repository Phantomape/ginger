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
    collect_experiment_id_sources,
    create_ticket,
    evaluate_gate,
    experiment_log_exists,
    experiment_id_exists_in_log,
    default_file_stem,
    iter_experiments,
    judge_results,
    locked_registry_update,
    load_registry,
    next_experiment_id,
    normalize_prediction,
    require_available_experiment_id,
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
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=["docs/"],
        evaluation_windows=[{"start": "2025-10-23", "end": "2026-04-21"}],
        exclusive_scope_ok=True,
    )
    second = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Make replay coverage measurable.",
        change_type="measurement_instrumentation",
        single_causal_variable="replay coverage bucket",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=["scripts/"],
        exclusive_scope_ok=True,
    )

    assert first["experiment_id"].endswith("-001")
    assert second["experiment_id"].endswith("-002")
    assert first["experiment_uid"].startswith("expuid-")
    assert first["experiment_uid"] != second["experiment_uid"]
    assert first["hub_identity"]["scheme"] == "hf_hub_local_v1"
    assert first["hub_identity"]["repo_id"] == (
        f"ginger/experiments/{first['experiment_id']}"
    )
    assert first["card_file"].endswith(f"cards/{first['experiment_id']}.md")
    assert first["revision_manifest_file"].endswith(
        f"manifests/{first['experiment_id']}.json"
    )
    assert first["status"] == "proposed"
    assert first["baseline_result_file"] == "data/backtests/backtest_results_20260425.json"
    card_path = tmp_path / "cards" / f"{first['experiment_id']}.md"
    manifest_path = tmp_path / "manifests" / f"{first['experiment_id']}.json"
    assert card_path.exists()
    assert manifest_path.exists()
    assert f"# Experiment Card: {first['experiment_id']}" in card_path.read_text(
        encoding="utf-8"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_type"] == "ginger_experiment_revision_manifest"
    assert manifest["experiment_id"] == first["experiment_id"]
    assert manifest["files"]["ticket"]["sha256"]
    assert manifest["files"]["card"]["sha256"]

    path = tmp_path / "registry.json"
    save_registry(registry, path)
    loaded = load_registry(path)
    assert len(loaded["experiments"]) == 2
    assert loaded["experiments"][0]["ticket_file"].endswith(
        f"tickets/{first['experiment_id']}.json"
    )


def test_create_ticket_auto_generates_per_experiment_write_scope(tmp_path):
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_tickets_dir": str(tmp_path / "tickets"),
    }

    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Find one reproducible failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="hold quality taxonomy",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
    )

    scopes = ticket["allowed_write_scope"]
    stem = f"{ticket['experiment_id'].replace('-', '_')}_hold_quality_taxonomy"
    assert f"quant/experiments/{stem}.py" in scopes
    assert f"data/experiments/{ticket['experiment_id']}/{stem}.json" in scopes
    assert f"experiments/tickets/{ticket['experiment_id']}.json" in scopes
    assert f"experiments/logs/{ticket['experiment_id']}.json" in scopes
    assert "data/" not in scopes


def test_next_experiment_id_scans_all_identity_sources(tmp_path):
    root = tmp_path
    (root / "docs").mkdir()
    (root / "data" / "experiments" / "exp-20990101-009").mkdir(parents=True)
    (root / "experiments" / "tickets").mkdir(parents=True)
    (root / "docs" / "experiments" / "tickets").mkdir(parents=True)
    (root / "experiments" / "logs").mkdir(parents=True)
    (root / "quant" / "experiments").mkdir(parents=True)

    (root / "docs" / "experiment_log.jsonl").write_text(
        json.dumps({"experiment_id": "exp-20990101-007"}) + "\n",
        encoding="utf-8",
    )
    (root / "experiments" / "tickets" / "exp-20990101-010.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-010"}),
        encoding="utf-8",
    )
    (root / "docs" / "experiments" / "tickets" / "exp-20990101-011.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-011"}),
        encoding="utf-8",
    )
    (root / "experiments" / "logs" / "exp-20990101-012.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-012"}),
        encoding="utf-8",
    )
    (root / "experiments" / "cards").mkdir(parents=True)
    (root / "experiments" / "cards" / "exp-20990101-014.md").write_text(
        "---\nexperiment_id: exp-20990101-014\n---\n",
        encoding="utf-8",
    )
    (root / "experiments" / "manifests").mkdir(parents=True)
    (root / "experiments" / "manifests" / "exp-20990101-015.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-015"}),
        encoding="utf-8",
    )
    (root / "quant" / "experiments" / "exp_20990101_013_runner.py").write_text(
        "EXPERIMENT_ID = 'exp-20990101-013'\n",
        encoding="utf-8",
    )
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "_repo_root": str(root),
        "experiments": [{"experiment_id": "exp-20990101-003"}],
    }

    sources = collect_experiment_id_sources(registry, root=root)

    assert "exp-20990101-007" in sources
    assert "exp-20990101-009" in sources
    assert "exp-20990101-011" in sources
    assert "exp-20990101-013" in sources
    assert "exp-20990101-014" in sources
    assert "exp-20990101-015" in sources
    assert next_experiment_id(registry, today="20990101", root=root) == "exp-20990101-016"


def test_create_ticket_rejects_explicit_id_already_seen_on_filesystem(tmp_path):
    root = tmp_path
    (root / "data" / "experiments" / "exp-20990101-004").mkdir(parents=True)
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_repo_root": str(root),
        "_tickets_dir": str(root / "experiments" / "tickets"),
    }

    try:
        create_ticket(
            registry,
            experiment_id="exp-20990101-004",
            lane="measurement_repair",
            hypothesis="Reserve an explicit ID only if the namespace is free.",
            change_type="identity_reservation",
            single_causal_variable="explicit reservation collision",
        )
    except ValueError as exc:
        assert "experiment_id already exists: exp-20990101-004" in str(exc)
        assert "data_experiment:path" in str(exc)
    else:
        raise AssertionError("filesystem-owned experiment_id was accepted")

    assert not (root / "experiments" / "tickets" / "exp-20990101-004.json").exists()


def test_create_ticket_reserves_explicit_unused_id_and_normalizes_format(tmp_path):
    root = tmp_path
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_repo_root": str(root),
        "_tickets_dir": str(root / "experiments" / "tickets"),
    }

    ticket = create_ticket(
        registry,
        experiment_id="exp_20990101_004",
        lane="measurement_repair",
        hypothesis="Reserve an explicit unused ID.",
        change_type="identity_reservation",
        single_causal_variable="explicit reservation",
    )

    assert ticket["experiment_id"] == "exp-20990101-004"
    assert ticket["hub_identity"]["repo_id"] == "ginger/experiments/exp-20990101-004"
    assert (root / "experiments" / "tickets" / "exp-20990101-004.json").exists()
    assert (root / "experiments" / "cards" / "exp-20990101-004.md").exists()
    assert (root / "experiments" / "manifests" / "exp-20990101-004.json").exists()


def test_require_available_experiment_id_reports_invalid_format():
    try:
        require_available_experiment_id("not-a-hub-id", {"experiments": []})
    except ValueError as exc:
        assert "exp-YYYYMMDD-NNN" in str(exc)
    else:
        raise AssertionError("invalid experiment_id was accepted")


def test_create_ticket_file_slug_overrides_auto_generated_file_stem():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Find one reproducible failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="bad trade hold-quality taxonomy",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        file_slug="hold_quality_audit",
    )

    stem = f"{ticket['experiment_id'].replace('-', '_')}_hold_quality_audit"
    assert f"quant/experiments/{stem}.py" in ticket["allowed_write_scope"]
    assert (
        f"data/experiments/{ticket['experiment_id']}/{stem}.json"
        in ticket["allowed_write_scope"]
    )


def test_create_ticket_records_trial_accounting_fields():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Mature one broad-market paper source.",
        change_type="default_off_paper_forward_maturation",
        single_causal_variable="broad-market replacement value ledger",
        mechanism_family="broad_market_leadership",
        trial_family="broad_market_forward_maturation",
        trial_variant_id="replacement_value_v1",
        changed_variable="broad_market_forward_ledger_fields",
        prior_trial_count=4,
        nearby_prior_experiments=["exp-20990101-001"],
        multiple_testing_risk_bucket="moderate",
        new_evidence_type="new_forward_rows",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
    )

    assert ticket["mechanism_family"] == "broad_market_leadership"
    assert ticket["trial_family"] == "broad_market_forward_maturation"
    assert ticket["trial_variant_id"] == "replacement_value_v1"
    assert ticket["changed_variable"] == "broad_market_forward_ledger_fields"
    assert ticket["prior_trial_count"] == 4
    assert ticket["nearby_prior_experiments"] == ["exp-20990101-001"]
    assert ticket["multiple_testing_risk_bucket"] == "moderate"
    assert ticket["new_evidence_type"] == "new_forward_rows"


def test_create_ticket_records_pre_run_prediction():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test one calibrated alpha hypothesis.",
        change_type="default_off_paper_allocation",
        single_causal_variable="calibrated alpha prediction",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction=normalize_prediction(
            success_probability=0.35,
            expected_ev_delta=0.12,
            expected_pnl_delta=2500.0,
            main_failure_modes=["sample_too_thin", "concentration_failed"],
            confidence_reason="Prior paper evidence is strong but forward rows are thin.",
        ),
    )

    prediction = ticket["prediction"]
    assert prediction["success_probability"] == 0.35
    assert prediction["expected_ev_delta"] == 0.12
    assert prediction["expected_pnl_delta"] == 2500.0
    assert prediction["main_failure_modes"] == [
        "sample_too_thin",
        "concentration_failed",
    ]
    assert prediction["recorded_at"]


def test_default_file_stem_falls_back_when_slug_has_no_ascii():
    assert default_file_stem("exp-20990101-001", "坏交易") == (
        "exp_20990101_001_experiment"
    )


def test_create_ticket_rejects_broad_directory_scope_without_exclusive_flag():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    try:
        create_ticket(
            registry,
            lane="loss_attribution",
            hypothesis="Find one reproducible failure family.",
            change_type="failure_taxonomy",
            single_causal_variable="hold quality taxonomy",
            baseline_result_file="data/backtests/backtest_results_20260425.json",
            allowed_write_scope=["quant/experiments/legacy/exp_loss_attribution_runner.py", "data/"],
        )
    except ValueError as exc:
        assert "broad allowed_write_scope" in str(exc)
        assert "data/" in str(exc)
    else:
        raise AssertionError("broad data/ scope was accepted")


def test_create_ticket_expands_scope_templates():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test one shadow source.",
        change_type="new_strategy_shadow",
        single_causal_variable="shadow source",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=[
            "quant/experiments/{experiment_id}_{lane}.py",
            "data/experiments/{experiment_id}/{change_type}.json",
        ],
    )

    assert ticket["allowed_write_scope"] == [
        f"quant/experiments/{ticket['experiment_id']}_alpha_discovery.py",
        f"data/experiments/{ticket['experiment_id']}/new_strategy_shadow.json",
    ]


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
        exclusive_scope_ok=True,
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
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=["scripts/"],
        exclusive_scope_ok=True,
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
    assert draft["trial_family"] == "measurement_instrumentation"
    assert draft["changed_variable"] == "log append path"
    assert draft["rejection_reason"] is None
    assert experiment_id_exists_in_log(log_path, ticket["experiment_id"])


def test_log_draft_includes_prediction_calibration():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="A confident alpha hypothesis fails.",
        change_type="default_off_paper_allocation",
        single_causal_variable="calibration failure",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction={
            "success_probability": 0.8,
            "expected_ev_delta": 0.2,
            "expected_pnl_delta": 4000.0,
            "main_failure_modes": ["sample_too_thin"],
            "confidence_reason": "Strong frozen-window paper evidence.",
        },
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0, "total_pnl": 1000.0},
        "after_metrics": {"expected_value_score": 0.9, "total_pnl": 700.0},
        "delta_metrics": {"expected_value_score": -0.1, "total_pnl": -300.0},
    }

    draft = build_log_draft(
        ticket,
        judgement,
        "data/before.json",
        "data/after.json",
        realized_failure_mode="sample_too_thin",
    )

    assert draft["prediction"]["success_probability"] == 0.8
    assert draft["calibration"]["actual_success"] == 0
    assert draft["calibration"]["calibration_direction"] == "overconfident"
    assert draft["calibration"]["brier_score"] == 0.64
    assert draft["calibration"]["ev_prediction_error"] == -0.3
    assert draft["calibration"]["predicted_failure_mode_hit"] is True


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
            baseline_result_file="data/backtests/backtest_results_20260425.json",
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


def test_locked_registry_update_uses_workspace_ticket_directory_for_docs_registry(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    registry_path = docs_dir / "experiment_registry.json"
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    def add_ticket(registry):
        return create_ticket(
            registry,
            lane="measurement_repair",
            hypothesis="Create ticket in workspace experiments directory.",
            change_type="logging_fix",
            single_causal_variable="ticket directory split brain",
            baseline_result_file="data/backtests/backtest_results_20260425.json",
        )

    ticket = locked_registry_update(registry_path, add_ticket)

    assert (tmp_path / "experiments" / "tickets" / f"{ticket['experiment_id']}.json").exists()
    assert not (tmp_path / "docs" / "experiments" / "tickets" / f"{ticket['experiment_id']}.json").exists()


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
                baseline_result_file="data/backtests/backtest_results_20260425.json",
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
        baseline_result_file="data/backtests/backtest_results_20260425.json",
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


def test_update_result_records_prediction_calibration():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="A low-confidence idea wins.",
        change_type="risk_scalar_or_topup",
        single_causal_variable="calibrated topup",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction={"success_probability": 0.2, "expected_ev_delta": 0.01},
    )
    judgement = {
        "decision": "accepted",
        "acceptance_reasons": ["expected_value_score improved 12.00%"],
        "delta_metrics": {"expected_value_score": 0.12},
    }

    updated = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "data/before.json",
        "data/after.json",
    )

    calibration = updated["result"]["calibration"]
    assert calibration["actual_success"] == 1
    assert calibration["calibration_direction"] == "underconfident"
    assert calibration["brier_score"] == 0.64
