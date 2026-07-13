import json
import importlib.util
import threading
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    append_log_entry,
    audit_experiment_process,
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


def alpha_prediction():
    return {
        "success_probability": 0.4,
        "main_failure_modes": ["thin_sample"],
        "confidence_reason": (
            "Mechanism has production visible PIT evidence, nearby trials were mixed, "
            "and thin sample or concentration can still fail."
        ),
    }


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
        prediction=alpha_prediction(),
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
            confidence_reason=(
                "Prior paper evidence is positive, related families were mixed, and "
                "forward rows may be too thin or concentrated."
            ),
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


def test_alpha_search_ticket_requires_prediction():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    try:
        create_ticket(
            registry,
            lane="alpha_search",
            hypothesis="Test one alpha hypothesis.",
            change_type="ranking_rule",
            single_causal_variable="new ranking field",
        )
    except ValueError as exc:
        assert "requires a pre-run prediction" in str(exc)
        assert "missing_prediction" in str(exc)
    else:
        raise AssertionError("alpha_search ticket without prediction was accepted")

    ticket = create_ticket(
        registry,
        lane="alpha_search",
        hypothesis="Test one alpha hypothesis.",
        change_type="ranking_rule",
        single_causal_variable="new ranking field",
        prediction=alpha_prediction(),
    )

    assert ticket["lane"] == "alpha_search"
    assert ticket["prediction"]["success_probability"] == 0.4


def test_alpha_ticket_prediction_requires_failure_modes():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    try:
        create_ticket(
            registry,
            lane="alpha_discovery",
            hypothesis="Test one alpha hypothesis.",
            change_type="risk_scalar_or_topup",
            single_causal_variable="new risk scalar",
            prediction={"success_probability": 0.5},
        )
    except ValueError as exc:
        assert "missing_main_failure_modes" in str(exc)
    else:
        raise AssertionError("alpha ticket without failure modes was accepted")


def test_alpha_ticket_prediction_requires_substantive_confidence_reason():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    for reason, expected in [
        ("TODO", "missing_substantive_confidence_reason"),
        ("Prior evidence is mixed.", "confidence_reason_too_short"),
    ]:
        try:
            create_ticket(
                registry,
                lane="alpha_search",
                hypothesis="Test one alpha hypothesis.",
                change_type="ranking_rule",
                single_causal_variable=f"new ranking field {expected}",
                prediction={
                    "success_probability": 0.35,
                    "main_failure_modes": ["thin_sample"],
                    "confidence_reason": reason,
                },
            )
        except ValueError as exc:
            assert "requires a substantive pre-run prediction" in str(exc)
            assert expected in str(exc)
        else:
            raise AssertionError("weak confidence reason was accepted")


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
        prediction=alpha_prediction(),
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
        prediction=alpha_prediction(),
    )
    second = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test conflicting breakout ranking key.",
        change_type="ranking_rule",
        single_causal_variable="breakout ranking key",
        allowed_write_scope=["quant/"],
        exclusive_scope_ok=True,
        prediction=alpha_prediction(),
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
        prediction=alpha_prediction(),
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
    shard = append_log_entry(log_path, draft)

    assert draft["status"] == "observed_only"
    assert draft["decision"] == "observed_only"
    assert draft["trial_family"] == "measurement_instrumentation"
    assert draft["changed_variable"] == "log append path"
    assert draft["rejection_reason"] is None
    # append_log_entry now persists to the per-experiment shard; the retired
    # monolithic log is no longer written.
    assert not log_path.exists()
    assert shard == tmp_path / "experiments" / "logs" / f"{ticket['experiment_id']}.json"
    assert (
        json.loads(shard.read_text(encoding="utf-8"))["experiment_id"]
        == ticket["experiment_id"]
    )


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
            "confidence_reason": (
                "Frozen-window paper evidence looks strong, but related support "
                "sleeves often failed when sample size was thin."
            ),
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


def test_log_draft_rejects_legacy_alpha_without_prediction():
    ticket = {
        "experiment_id": "exp-20990101-020",
        "lane": "alpha_search",
        "hypothesis": "Legacy hand-written alpha ticket.",
        "change_type": "ranking_rule",
        "single_causal_variable": "legacy missing prediction",
    }
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 0.9},
        "delta_metrics": {"expected_value_score": -0.1},
    }

    try:
        build_log_draft(ticket, judgement, "before.json", "after.json")
    except ValueError as exc:
        assert "requires a pre-run prediction" in str(exc)
    else:
        raise AssertionError("legacy alpha closeout without prediction was accepted")

    draft = build_log_draft(
        ticket,
        judgement,
        "before.json",
        "after.json",
        allow_missing_prediction=True,
    )
    assert draft["experiment_id"] == "exp-20990101-020"
    assert "prediction" not in draft


def test_audit_experiment_process_reports_legacy_without_failing(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20260528-008.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260528-008",
                "lane": "alpha_search",
                "status": "accepted_legacy_stub",
                "updated_at": "2026-05-28T05:36:40+00:00",
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20260528-008.json").write_text(
        json.dumps({"experiment_id": "exp-20260528-008", "decision": "accepted"}),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    assert audit["passed"] is True
    assert audit["closed_legacy_pre_enforcement_missing_prediction_count"] == 1
    assert audit["closed_post_enforcement_missing_prediction_count"] == 0
    assert audit["closed_legacy_pre_enforcement_missing_calibration_count"] == 1
    assert audit["closed_post_enforcement_missing_calibration_count"] == 0


def test_audit_experiment_process_fails_post_enforcement_gaps(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20990101-030.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-030",
                "lane": "alpha_search",
                "status": "accepted_post_enforcement_stub",
                "created_at": "2099-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20990101-030.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-030", "decision": "accepted"}),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert audit["post_enforcement_missing_prediction_count"] == 1
    assert audit["closed_post_enforcement_missing_prediction_count"] == 1
    assert audit["closed_post_enforcement_missing_calibration_count"] == 1
    assert audit["post_enforcement_missing_prediction_examples"][0][
        "experiment_id"
    ] == "exp-20990101-030"


def test_lean_audit_flags_weak_reasoning_and_missing_reflection(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20990101-040.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-040",
                "lane": "alpha_search",
                "status": "accepted",
                "created_at": "2099-01-01T00:00:00+00:00",
                "prediction": {
                    "success_probability": 0.4,
                    "main_failure_modes": ["thin_sample"],
                    "confidence_reason": "Maybe works.",
                },
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20990101-040.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-040",
                "decision": "accepted",
                "calibration": {"actual_success": 1},
                "post_run_reflection": {
                    "why_result_happened": "TODO",
                    "forbidden_near_neighbor_retry": "TODO",
                    "new_evidence_required": "TODO",
                },
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        lean=True,
    )

    assert audit["passed"] is False
    assert audit["lean_quality_passed"] is False
    assert audit["post_enforcement_weak_prediction_quality_count"] == 1
    assert audit["closed_post_enforcement_weak_reflection_count"] == 1


def test_lean_audit_reports_legacy_debt_without_blocking(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20260607-002.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260607-002",
                "lane": "alpha_search",
                "status": "rejected",
                "created_at": "2026-06-07T01:18:00+00:00",
                "prediction": {
                    "success_probability": 0.4,
                    "main_failure_modes": ["thin_sample"],
                    "confidence_reason": "Maybe works.",
                },
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20260607-002.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260607-002",
                "decision": "rejected",
                "calibration": {"actual_success": 0},
                "post_run_reflection": {
                    "why_result_happened": "TODO",
                    "forbidden_near_neighbor_retry": "TODO",
                    "new_evidence_required": "TODO",
                },
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        lean=True,
    )

    assert audit["passed"] is True
    assert audit["lean_quality_passed"] is True
    assert audit["weak_prediction_quality_count"] == 1
    assert audit["post_enforcement_weak_prediction_quality_count"] == 0
    assert audit["closed_weak_reflection_count"] == 1
    assert audit["closed_post_enforcement_weak_reflection_count"] == 0


def test_lean_audit_passes_substantive_reasoning_and_reflection(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20990101-041.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-041",
                "lane": "alpha_search",
                "status": "accepted",
                "created_at": "2099-01-01T00:00:00+00:00",
                "prediction": {
                    "success_probability": 0.34,
                    "main_failure_modes": ["drawdown_drift", "window_regression"],
                    "confidence_reason": (
                        "Peer-shock rows previously improved all windows, but "
                        "this variant may fail if it duplicates selected consensus flow."
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20990101-041.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-041",
                "decision": "accepted",
                "calibration": {"actual_success": 1},
                "post_run_reflection": {
                    "why_result_happened": (
                        "The policy worked because peer-shock rows added "
                        "independent relation evidence instead of duplicating "
                        "the accepted consensus source family."
                    ),
                    "forbidden_near_neighbor_retry": (
                        "Do not retune correlation thresholds on the same windows."
                    ),
                    "new_evidence_required": (
                        "Retry only with closed forward replacement-value rows "
                        "or a new PIT peer-classification source."
                    ),
                },
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        lean=True,
    )

    assert audit["passed"] is True
    assert audit["lean_quality_passed"] is True
    assert audit["post_enforcement_weak_prediction_quality_count"] == 0
    assert audit["closed_post_enforcement_weak_reflection_count"] == 0


def test_per_experiment_log_entry_is_written_to_own_file(tmp_path):
    row = {"experiment_id": "exp-20990101-003", "decision": "observed_only"}
    logs_dir = tmp_path / "logs"

    path = save_experiment_log_entry(row, logs_dir=logs_dir)

    assert path == logs_dir / "exp-20990101-003.json"
    assert experiment_log_exists("exp-20990101-003", logs_dir=logs_dir)
    assert json.loads(path.read_text(encoding="utf-8"))["decision"] == "observed_only"


def test_per_experiment_log_entry_rejects_expected_identity_mismatch(tmp_path):
    row = {"experiment_id": "exp-20990101-002", "decision": "observed_only"}
    logs_dir = tmp_path / "logs"

    with pytest.raises(ValueError, match="experiment log identity mismatch"):
        save_experiment_log_entry(
            row,
            expected_experiment_id="exp-20990101-017",
            logs_dir=logs_dir,
        )

    assert not logs_dir.exists()


def test_mortgage_wrapper_rebinds_inherited_compact_log_identity(monkeypatch):
    runner = (
        ROOT
        / "quant"
        / "experiments"
        / "exp_20260711_017_mortgage_rate_relief_residential_leadership.py"
    )
    spec = importlib.util.spec_from_file_location("mortgage_log_identity_test", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = module.prior.scaffold.prior.base
    monkeypatch.setattr(
        base,
        "compact_log",
        lambda payload: {
            "experiment_id": "exp-20260711-002",
            "artifact": "data/experiments/exp-20260711-002/stale.json",
            "log": "experiments/logs/exp-20260711-002.json",
            "hypothesis": "stale MOVE identity",
        },
    )

    row = module.build_log_record({})

    assert row["experiment_id"] == "exp-20260711-017"
    assert row["hypothesis"] == module.HYPOTHESIS
    assert row["changed_variable"] == module.CHANGED_VARIABLE
    assert row["artifact"].startswith("data/experiments/exp-20260711-017/")
    assert row["log"] == "experiments/logs/exp-20260711-017.json"


def test_append_log_entry_is_idempotent_on_repeat(tmp_path):
    # The retired monolithic appender now writes the per-experiment shard and is
    # idempotent: a repeat (e.g. the runner already wrote its own shard) is a
    # no-op rather than a duplicate error.
    row = {"experiment_id": "exp-20990101-001", "decision": "observed_only"}
    log_path = tmp_path / "experiment_log.jsonl"
    first = append_log_entry(log_path, row)
    second = append_log_entry(log_path, row)

    assert first == second
    assert first.exists()
    assert not log_path.exists()


def test_append_log_entry_writes_shards_not_monolithic_log(tmp_path):
    log_path = tmp_path / "experiment_log.jsonl"
    first = append_log_entry(
        log_path, {"experiment_id": "exp-20990101-002", "decision": "observed_only"}
    )
    second = append_log_entry(
        log_path,
        {"experiment_id": "exp-20990101-003", "decision": "observed_only"},
    )

    logs_dir = tmp_path / "experiments" / "logs"
    assert first == logs_dir / "exp-20990101-002.json"
    assert second == logs_dir / "exp-20990101-003.json"
    assert first.exists() and second.exists()
    # The retired monolithic log is never written.
    assert not log_path.exists()


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
        prediction={
            "success_probability": 0.2,
            "expected_ev_delta": 0.01,
            "main_failure_modes": ["drawdown_failed"],
            "confidence_reason": (
                "Low-confidence top-up may help if drawdown stays contained, but "
                "nearby risk-scalar trials often failed tail-risk guards."
            ),
        },
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


def test_looks_placeholder_word_boundary():
    from experiment_registry import _looks_placeholder

    # Real prose containing placeholder words as substrings must pass.
    assert _looks_placeholder(
        "backfilled pre-2023 index history raises episode count; nonetheless "
        "the sample stays thin"
    ) is False
    # Bare placeholders must still be caught.
    assert _looks_placeholder("TODO") is True
    assert _looks_placeholder("fill in later") is True
    assert _looks_placeholder("none") is True
    assert _looks_placeholder("") is True
