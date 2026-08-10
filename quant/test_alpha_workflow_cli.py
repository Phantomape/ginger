from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts import alpha_workflow as workflow


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "scripts" / "alpha_workflow.py"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _proposal() -> dict:
    return {
        "lane": "alpha_search",
        "hypothesis": "A bounded research lead may have positive replacement value.",
        "change_type": "private_replay_scout",
        "single_causal_variable": "bounded_research_lead_v1",
        "causal_components": [
            "first component contains an embedded comma, which must remain intact",
            "second fixed component",
        ],
        "mechanism_family": "bounded_mechanism",
        "trial_family": "bounded_trial",
        "changed_variable": "bounded_research_lead_v1",
        "prediction": {
            "success_probability": 0.25,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
            "main_failure_modes": ["no replacement value"],
            "confidence_reason": (
                "The mechanism is explicit but the evidence remains a research lead, "
                "so success is deliberately estimated below one in three."
            ),
        },
    }


def _scope(expected: int) -> dict:
    return {
        "preregistered_at": "2026-08-04T16:00:00Z",
        "data_cutoff": "2026-08-04T16:30:00Z",
        "freeze_at": "2026-08-04T18:00:00Z",
        "expected_candidate_count": expected,
    }


def _normalised_card(disposition: str = "test") -> dict:
    return {
        "card_id": "itrc-test",
        "created_at": "2026-08-04T17:00:00Z",
        "data_cutoff": "2026-08-04T16:30:00Z",
        "decision": {
            "disposition": disposition,
            "next_machine_action": "run_d0_d3" if disposition == "test" else "park",
        },
    }


def _guard_receipt() -> dict:
    return {
        "enforced": True,
        "data_source_unclassified": False,
        "fingerprint": {"data_source": "test_source", "gate_shape": "candidate_pool"},
        "source_saturation": {
            "applicable": False,
            "saturated": False,
            "source": "test_source",
            "gate_shape": "candidate_pool",
            "trials": 0,
        },
        "reopen_condition_guard": {"applicable": True, "blocked": False},
        "observed_only_streak_guard": {"applicable": False, "blocked": False},
        "routine_materialization_guard": {"applicable": False, "blocked": False},
        "recipe_lane_guard": {"applicable": False, "blocked": False},
        "in_flight_duplicate_guard": {"applicable": True, "blocked": False},
    }


def _qualify_args(tmp_path: Path, *, proposal: bool = True) -> argparse.Namespace:
    return argparse.Namespace(
        card=["inputs/card.json"],
        scope_manifest="inputs/scope.json",
        surfaces="inputs/surfaces.json",
        prior_fingerprints="inputs/prior.json",
        proposal="inputs/proposal.json" if proposal else None,
        output_dir="outputs/qualification",
    )


def test_help_exposes_only_three_operator_commands() -> None:
    process = subprocess.run(
        [sys.executable, "-B", str(CLI), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0
    assert "{qualify,start,finish}" in process.stdout


def test_qualify_collapses_redundant_validation_commands(tmp_path: Path) -> None:
    _write(tmp_path / "inputs" / "card.json", {"raw": True})
    _write(tmp_path / "inputs" / "scope.json", _scope(1))
    _write(tmp_path / "inputs" / "surfaces.json", {"surfaces": []})
    _write(tmp_path / "inputs" / "prior.json", {"snapshot": True})
    _write(tmp_path / "inputs" / "proposal.json", _proposal())
    commands: list[str] = []

    def fake_run(command: list[str]) -> dict:
        action = command[3]
        commands.append(action)
        if action == "normalise":
            return _normalised_card()
        if action == "project":
            return {"candidate_id": "cand-test", "evidence_grade": "lead"}
        if action == "build-panel":
            return {"selected_candidate_id": "cand-test", "preflight_decisions": {}}
        if action == "build-promotion":
            return {
                "record_type": "alpha_experiment_promotion_request",
                "proposal": _proposal(),
                "promotion_hash": "a" * 64,
                "outcome_blind": True,
                "trade_enabled": False,
            }
        raise AssertionError(command)

    result = workflow.qualify(
        _qualify_args(tmp_path), run_json=fake_run, repo_root=tmp_path
    )

    assert result["disposition"] == "promoted"
    assert result["experiment_id_reserved"] is False
    assert commands == ["normalise", "project", "build-panel", "build-promotion"]
    assert "validate" not in commands
    assert "preflight" not in commands
    assert "verify-panel" not in commands
    receipt = json.loads(
        (tmp_path / "outputs" / "qualification" / "qualification.json").read_text()
    )
    assert receipt["receipt_hash"] == workflow._receipt_hash(receipt)


def test_qualify_park_is_normal_zero_id_result(tmp_path: Path) -> None:
    _write(tmp_path / "inputs" / "card.json", {"raw": True})
    _write(tmp_path / "inputs" / "scope.json", _scope(1))
    _write(tmp_path / "inputs" / "surfaces.json", {"surfaces": []})
    _write(tmp_path / "inputs" / "prior.json", {"snapshot": True})
    calls = 0

    def fake_run(command: list[str]) -> dict:
        nonlocal calls
        calls += 1
        assert command[3] == "normalise"
        return _normalised_card("park")

    result = workflow.qualify(
        _qualify_args(tmp_path, proposal=False),
        run_json=fake_run,
        repo_root=tmp_path,
    )

    assert calls == 1
    assert result["disposition"] == "no_candidate"
    assert result["experiment_id_reserved"] is False
    assert "promotion" not in result["artifacts"]


def _qualification_fixture(tmp_path: Path) -> Path:
    promotion_path = tmp_path / "qualified" / "promotion.json"
    _write(
        promotion_path,
        {
            "record_type": "alpha_experiment_promotion_request",
            "proposal": _proposal(),
            "promotion_hash": "b" * 64,
        },
    )
    receipt = workflow._qualification_receipt(
        disposition="promoted",
        cards=[],
        artifacts={"promotion": workflow._artifact(promotion_path, repo_root=tmp_path)},
        candidate_count=1,
        selected_candidate_id="cand-test",
    )
    qualification_path = tmp_path / "qualified" / "qualification.json"
    _write(qualification_path, receipt)
    return qualification_path


def _execution_fixture(tmp_path: Path) -> Path:
    baseline = tmp_path / "data" / "baseline.json"
    _write(baseline, {"baseline": True})
    spec = {
        "schema_version": 1,
        "record_type": "alpha_workflow_execution_spec",
        "baseline_result_file": "data/baseline.json",
        "allowed_write_scope": ["quant/experiments/{experiment_id}_runner.py"],
        "must_not_touch": ["quant/run.py"],
        "locked_variables": ["entry_policy"],
        "evaluation_windows": [],
        "acceptance_rule": "Use the ticket's predeclared falsifier and repository gates.",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_data_source",
    }
    path = tmp_path / "qualified" / "execution.json"
    _write(path, spec)
    return path


def test_start_preserves_exact_proposal_lists_and_claims(tmp_path: Path) -> None:
    qualification = _qualification_fixture(tmp_path)
    execution = _execution_fixture(tmp_path)
    registry = tmp_path / "docs" / "experiment_registry.json"
    _write(registry, {"experiments": []})
    captured: dict = {}

    def fake_reserve(registry_path: str, **kwargs: object) -> dict:
        captured.update(kwargs)
        ticket = {
            "experiment_id": "exp-20260805-010",
            "experiment_uid": "expuid-test",
            "status": "proposed",
            "owner": "codex",
        }
        _write(
            tmp_path / "experiments" / "tickets" / "exp-20260805-010.json",
            ticket,
        )
        return ticket

    def fake_claim(
        registry_path: str, experiment_id: str, owner: str, *, force: bool
    ) -> tuple[dict, list]:
        assert force is False
        return (
            {
                "experiment_id": experiment_id,
                "experiment_uid": "expuid-test",
                "status": "claimed",
                "owner": owner,
            },
            [],
        )

    args = argparse.Namespace(
        qualification=str(qualification.relative_to(tmp_path)),
        execution_spec=str(execution.relative_to(tmp_path)),
        owner="codex",
        registry="docs/experiment_registry.json",
    )
    result = workflow.start(
        args,
        repo_root=tmp_path,
        novelty_check=lambda _: _guard_receipt(),
        reserve=fake_reserve,
        claim=fake_claim,
    )

    assert result["status"] == "claimed"
    assert captured["causal_components"] == _proposal()["causal_components"]
    assert captured["promotion_request"] == "qualified/promotion.json"
    assert captured["exclusive_scope_ok"] is False


def test_start_exact_retry_reuses_id_and_guard_ignores_only_itself(tmp_path: Path) -> None:
    qualification = _qualification_fixture(tmp_path)
    execution = _execution_fixture(tmp_path)
    registry = tmp_path / "docs" / "experiment_registry.json"
    _write(registry, {"experiments": []})
    ticket_path = tmp_path / "experiments" / "tickets" / "exp-20260805-011.json"
    seen_guard_ids: list[str | None] = []

    def fake_reserve(registry_path: str, **kwargs: object) -> dict:
        intent = workflow.reservation_intent_for(kwargs)
        if ticket_path.exists():
            return json.loads(ticket_path.read_text())
        ticket = {
            "experiment_id": "exp-20260805-011",
            "experiment_uid": "expuid-retry",
            "status": "proposed",
            "owner": "codex",
            "reservation_intent": {
                "schema_version": 1,
                "key": intent["key"],
                "payload_hash": intent["payload_hash"],
            },
        }
        _write(ticket_path, ticket)
        return ticket

    def fake_claim(
        registry_path: str, experiment_id: str, owner: str, *, force: bool
    ) -> tuple[dict, list]:
        ticket = json.loads(ticket_path.read_text())
        ticket["status"] = "claimed"
        _write(ticket_path, ticket)
        return ticket, []

    def fake_novelty(namespace: argparse.Namespace) -> dict:
        seen_guard_ids.append(namespace.experiment_id)
        return _guard_receipt()

    args = argparse.Namespace(
        qualification=str(qualification.relative_to(tmp_path)),
        execution_spec=str(execution.relative_to(tmp_path)),
        owner="codex",
        registry="docs/experiment_registry.json",
    )
    first = workflow.start(
        args,
        repo_root=tmp_path,
        novelty_check=fake_novelty,
        reserve=fake_reserve,
        claim=fake_claim,
        revalidate_promotion=lambda *args, **kwargs: None,
    )
    second = workflow.start(
        args,
        repo_root=tmp_path,
        novelty_check=fake_novelty,
        reserve=fake_reserve,
        claim=fake_claim,
        revalidate_promotion=lambda *args, **kwargs: None,
    )

    assert first["experiment_id"] == second["experiment_id"] == "exp-20260805-011"
    assert first["reused_reservation"] is False
    assert second["reused_reservation"] is True
    assert seen_guard_ids == [None, "exp-20260805-011"]

    terminal = json.loads(ticket_path.read_text())
    terminal["status"] = "rejected"
    terminal["result"] = {"decision": "rejected"}
    _write(ticket_path, terminal)
    try:
        workflow.start(
            args,
            repo_root=tmp_path,
            novelty_check=fake_novelty,
            reserve=fake_reserve,
            claim=fake_claim,
            revalidate_promotion=lambda *args, **kwargs: None,
        )
    except workflow.WorkflowError as exc:
        assert exc.code == "qualification_already_consumed"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("a terminal ticket must permanently consume its qualification")


def test_start_rejects_tampered_qualification_before_reserve(tmp_path: Path) -> None:
    qualification = _qualification_fixture(tmp_path)
    execution = _execution_fixture(tmp_path)
    registry = tmp_path / "docs" / "experiment_registry.json"
    _write(registry, {"experiments": []})
    promotion = tmp_path / "qualified" / "promotion.json"
    promotion.write_text("{}", encoding="utf-8")
    called = False

    def fake_reserve(*args: object, **kwargs: object) -> dict:
        nonlocal called
        called = True
        raise AssertionError("reserve must not run")

    args = argparse.Namespace(
        qualification=str(qualification.relative_to(tmp_path)),
        execution_spec=str(execution.relative_to(tmp_path)),
        owner="codex",
        registry="docs/experiment_registry.json",
    )
    try:
        workflow.start(
            args,
            repo_root=tmp_path,
            novelty_check=lambda _: {"enforced": True},
            reserve=fake_reserve,
        )
    except workflow.WorkflowError as exc:
        assert exc.code == "qualification_artifact_tampered"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("tampered qualification should fail")
    assert called is False


def test_start_fails_closed_when_dynamic_guard_receipt_is_incomplete(
    tmp_path: Path,
) -> None:
    qualification = _qualification_fixture(tmp_path)
    execution = _execution_fixture(tmp_path)
    _write(tmp_path / "docs" / "experiment_registry.json", {"experiments": []})
    reserved = False

    def fake_reserve(*args: object, **kwargs: object) -> dict:
        nonlocal reserved
        reserved = True
        raise AssertionError("an incomplete guard receipt must block reservation")

    args = argparse.Namespace(
        qualification=str(qualification.relative_to(tmp_path)),
        execution_spec=str(execution.relative_to(tmp_path)),
        owner="codex",
        registry="docs/experiment_registry.json",
    )
    try:
        workflow.start(
            args,
            repo_root=tmp_path,
            novelty_check=lambda _: {"enforced": True},
            reserve=fake_reserve,
        )
    except workflow.WorkflowError as exc:
        assert exc.code == "start_guard_unavailable"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("incomplete guards should fail closed")
    assert reserved is False


def test_new_unclassified_source_requires_same_ticket_classifier_coverage() -> None:
    receipt = _guard_receipt()
    receipt["data_source_unclassified"] = True
    spec = {
        "new_evidence_type": "new_data_source",
        "allowed_write_scope": ["scripts/experiment_fingerprint.py"],
    }

    accepted = workflow._require_guard_receipt_health(
        receipt,
        lane="alpha_search",
        spec=spec,
    )
    assert accepted["alpha_workflow_guard_health"][
        "classifier_coverage_required"
    ] is True

    try:
        workflow._require_guard_receipt_health(
            receipt,
            lane="alpha_search",
            spec={"new_evidence_type": "new_data_source", "allowed_write_scope": []},
        )
    except workflow.WorkflowError as exc:
        assert exc.code == "classifier_coverage_required"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("unclassified sources must repair classifier coverage")


def _finish_args() -> argparse.Namespace:
    return argparse.Namespace(
        experiment_id="exp-20260805-020",
        before="data/before.json",
        after="data/after.json",
        reflection_file="data/reflection.json",
        registry="docs/experiment_registry.json",
        reject=False,
    )


def _reflection() -> dict:
    return {
        "change_summary": "Added one bounded facade while leaving all strategy behavior unchanged.",
        "why_result_happened": (
            "The measured result was flat because orchestration changed but strategy inputs, "
            "orders, and Gate metrics remained intentionally identical throughout the run."
        ),
        "realized_failure_mode": "No strategy failure; only orchestration behavior was evaluated.",
        "forbidden_near_neighbor_retry": (
            "Do not add another wrapper that repeats the same reserve, claim, or close semantics."
        ),
        "new_evidence_required": (
            "A retry requires a newly observed operator failure or a changed lifecycle contract."
        ),
    }


def _judgement(before: Path, after: Path) -> dict:
    return {
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 1.0},
        "delta_metrics": {"expected_value_score": 0.0},
        "decision": "rejected",
        "acceptance_reasons": [],
    }


def _alpha_ticket() -> dict:
    return {
        "experiment_id": "exp-20260805-020",
        "experiment_uid": "expuid-finish",
        "lane": "alpha_search",
        "status": "claimed",
        "hypothesis": "A bounded alpha hypothesis is evaluated without changing other policies.",
        "change_type": "candidate_pool",
        "mechanism_family": "bounded_finish_test",
        "trial_family": "bounded_finish_test",
        "changed_variable": "candidate_pool",
        "causal_components": ["one bounded candidate pool"],
        "allowed_write_scope": ["quant/experiments/test.py"],
        "locked_variables": ["entry_policy"],
        "evaluation_windows": [],
        "prediction": {
            "success_probability": 0.2,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": ["no replacement value"],
            "confidence_reason": (
                "The mechanism is bounded and measurable, but prior evidence remains weak "
                "enough that failure is substantially more likely than success."
            ),
        },
        "result": None,
    }


def _prepare_finish_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write(tmp_path / "docs" / "experiment_registry.json", {"experiments": []})
    before = tmp_path / "data" / "before.json"
    after = tmp_path / "data" / "after.json"
    reflection = tmp_path / "data" / "reflection.json"
    _write(before, {"before": True})
    _write(after, {"after": True})
    _write(reflection, _reflection())
    return before, after, reflection


def _terminal_ticket_with_intent(tmp_path: Path, *, write_log: bool) -> dict:
    before, after, _ = _prepare_finish_inputs(tmp_path)
    ticket = _alpha_ticket()
    request = workflow._finish_request(
        ticket,
        before=before,
        after=after,
        reflection=_reflection(),
        force_reject=False,
        repo_root=tmp_path,
    )
    intent = workflow._build_finish_intent(
        ticket,
        request,
        before=before,
        after=after,
        reflection=_reflection(),
        force_reject=False,
        judge=_judgement,
    )
    ticket["status"] = "rejected"
    ticket["result"] = {
        "decision": "rejected",
        "before_result_file": "data/before.json",
        "after_result_file": "data/after.json",
    }
    ticket["alpha_workflow_finish_intent"] = intent
    _write(
        tmp_path / "experiments" / "tickets" / "exp-20260805-020.json",
        ticket,
    )
    if write_log:
        _write(
            tmp_path / "experiments" / "logs" / "exp-20260805-020.json",
            intent["log_row"],
        )
    return intent


def test_finish_terminal_retry_skips_close_and_runs_maintenance(tmp_path: Path) -> None:
    _terminal_ticket_with_intent(tmp_path, write_log=True)
    commands: list[list[str]] = []

    def fake_process(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "{}", "")

    result, code = workflow.finish(
        _finish_args(), run_process=fake_process, repo_root=tmp_path
    )

    assert code == 0
    assert result["already_closed"] is True
    assert result["log_recovered"] is False
    assert len(commands) == 3
    assert any("build_frozen_families.py" in part for part in commands[0])
    assert any("build_alpha_memory.py" in part for part in commands[1])
    assert "audit" in commands[2]
    assert all("close" not in command for command in commands)


def test_finish_closes_then_audits(tmp_path: Path) -> None:
    _prepare_finish_inputs(tmp_path)
    ticket_path = tmp_path / "experiments" / "tickets" / "exp-20260805-020.json"
    _write(ticket_path, _alpha_ticket())
    commands: list[list[str]] = []
    update_calls = 0

    def fake_process(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "{}", "")

    def fake_update(
        registry_path: str,
        experiment_id: str,
        judgement: dict,
        before: Path,
        after: Path,
        **kwargs: object,
    ) -> dict:
        nonlocal update_calls
        update_calls += 1
        assert kwargs["status_override"] == "rejected"
        ticket = json.loads(ticket_path.read_text())
        ticket["status"] = "rejected"
        ticket["result"] = {
            "decision": "rejected",
            "before_result_file": "data/before.json",
            "after_result_file": "data/after.json",
        }
        _write(ticket_path, ticket)
        return ticket

    def fake_save(row: dict, **kwargs: object) -> Path:
        path = tmp_path / "experiments" / "logs" / "exp-20260805-020.json"
        _write(path, row)
        return path

    result, code = workflow.finish(
        _finish_args(),
        run_process=fake_process,
        judge=_judgement,
        update_result=fake_update,
        save_log=fake_save,
        repo_root=tmp_path,
    )

    assert code == 0
    assert result["already_closed"] is False
    assert result["log_recovered"] is True
    assert update_calls == 1
    assert len(commands) == 3
    assert "audit" in commands[2]
    assert all("close" not in command for command in commands)


def test_finish_recovers_missing_log_without_reclosing(tmp_path: Path) -> None:
    intent = _terminal_ticket_with_intent(tmp_path, write_log=False)
    updates = 0

    def fail_update(*args: object, **kwargs: object) -> dict:
        nonlocal updates
        updates += 1
        raise AssertionError("terminal retry must not close again")

    def fake_save(row: dict, **kwargs: object) -> Path:
        assert workflow._canonical_hash(row) == intent["log_row_hash"]
        path = tmp_path / "experiments" / "logs" / "exp-20260805-020.json"
        _write(path, row)
        return path

    def fake_process(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "{}", "")

    result, code = workflow.finish(
        _finish_args(),
        run_process=fake_process,
        update_result=fail_update,
        save_log=fake_save,
        repo_root=tmp_path,
    )

    assert code == 0
    assert updates == 0
    assert result["already_closed"] is True
    assert result["log_recovered"] is True


def test_finish_rejects_terminal_result_from_different_artifacts(tmp_path: Path) -> None:
    _terminal_ticket_with_intent(tmp_path, write_log=False)
    _write(tmp_path / "data" / "other_before.json", {"other": True})
    ticket_path = tmp_path / "experiments" / "tickets" / "exp-20260805-020.json"
    ticket = json.loads(ticket_path.read_text())
    ticket["result"]["before_result_file"] = "data/other_before.json"
    _write(ticket_path, ticket)

    try:
        workflow.finish(
            _finish_args(),
            run_process=lambda command: subprocess.CompletedProcess(
                command, 0, "{}", ""
            ),
            repo_root=tmp_path,
        )
    except workflow.WorkflowError as exc:
        assert exc.code == "finish_terminal_conflict"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("a different low-level close must not acquire the bound log")

    assert not (tmp_path / "experiments" / "logs" / "exp-20260805-020.json").exists()


def test_finish_uses_real_registry_close_and_log_interfaces(tmp_path: Path) -> None:
    _prepare_finish_inputs(tmp_path)
    ticket_path = tmp_path / "experiments" / "tickets" / "exp-20260805-020.json"
    ticket = _alpha_ticket()
    ticket["ticket_file"] = "experiments/tickets/exp-20260805-020.json"
    _write(ticket_path, ticket)

    def fake_process(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "{}", "")

    result, code = workflow.finish(
        _finish_args(),
        run_process=fake_process,
        judge=_judgement,
        repo_root=tmp_path,
    )

    closed = json.loads(ticket_path.read_text())
    log = json.loads(
        (tmp_path / "experiments" / "logs" / "exp-20260805-020.json").read_text()
    )
    assert code == 0
    assert result["status"] == "rejected"
    assert closed["status"] == closed["result"]["decision"] == "rejected"
    assert closed["alpha_workflow_finish_intent"]["log_row_hash"] == (
        workflow._canonical_hash(log)
    )
