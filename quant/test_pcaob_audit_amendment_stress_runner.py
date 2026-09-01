import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "quant"
    / "experiments"
    / "exp-20260901-001_pcaob_audit_amendment_stress_h5.py"
)
SPEC = importlib.util.spec_from_file_location(
    "pcaob_audit_amendment_stress_runner", RUNNER_PATH
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _claimed_ticket():
    return {
        "experiment_id": runner.EXPERIMENT_ID,
        "status": "claimed",
        "owner": runner.OWNER,
        "completed_at": None,
        "result": None,
    }


def _isolate_outputs(monkeypatch, tmp_path):
    paths = {
        "raw": tmp_path / "raw.json",
        "artifact": tmp_path / "result.json",
        "log": tmp_path / "log.json",
        "registry": tmp_path / "registry.json",
        "ticket": tmp_path / "ticket.json",
    }
    monkeypatch.setattr(runner, "RAW_INPUT", paths["raw"])
    monkeypatch.setattr(runner, "ARTIFACT", paths["artifact"])
    monkeypatch.setattr(runner, "LOG", paths["log"])
    monkeypatch.setattr(runner, "REGISTRY", paths["registry"])
    monkeypatch.setattr(runner, "TICKET", paths["ticket"])
    return paths


def test_single_run_guard_accepts_only_after_strict_anchor_validation(
    tmp_path, monkeypatch
):
    paths = _isolate_outputs(monkeypatch, tmp_path)
    calls = []

    def validate(registry_path, ticket):
        calls.append((registry_path, ticket))

    monkeypatch.setattr(
        runner, "_validate_file_backed_reservation_anchors", validate
    )
    ticket = _claimed_ticket()

    runner._verify_single_run_state(ticket)

    assert calls == [(paths["registry"], ticket)]
    assert all(not path.exists() for path in paths.values())


@pytest.mark.parametrize(
    "ticket_update",
    [
        {"status": "rejected", "completed_at": "2099-01-01T00:00:00Z"},
        {"result": {"decision": "rejected"}},
        {"owner": "different-owner"},
    ],
)
def test_single_run_guard_rejects_terminal_or_wrong_owner_before_anchor_read(
    tmp_path, monkeypatch, ticket_update
):
    _isolate_outputs(monkeypatch, tmp_path)
    ticket = _claimed_ticket()
    ticket.update(ticket_update)

    def unexpected_anchor_read(*_args, **_kwargs):
        raise AssertionError("terminal state reached anchor validation")

    monkeypatch.setattr(
        runner,
        "_validate_file_backed_reservation_anchors",
        unexpected_anchor_read,
    )

    with pytest.raises(runner.ContaminationError):
        runner._verify_single_run_state(ticket)


@pytest.mark.parametrize("existing_key", ["raw", "artifact", "log"])
def test_single_run_guard_rejects_existing_output_without_overwrite(
    tmp_path, monkeypatch, existing_key
):
    paths = _isolate_outputs(monkeypatch, tmp_path)
    original = b"immutable-existing-output\n"
    paths[existing_key].write_bytes(original)

    def unexpected_anchor_read(*_args, **_kwargs):
        raise AssertionError("existing output reached anchor validation")

    monkeypatch.setattr(
        runner,
        "_validate_file_backed_reservation_anchors",
        unexpected_anchor_read,
    )

    with pytest.raises(runner.ContaminationError, match="already exists"):
        runner._verify_single_run_state(_claimed_ticket())

    assert paths[existing_key].read_bytes() == original


def test_single_run_guard_rejects_incomplete_111_without_outputs(
    tmp_path, monkeypatch
):
    paths = _isolate_outputs(monkeypatch, tmp_path)

    def incomplete_claim(*_args, **_kwargs):
        raise ValueError("ever-claimed lifecycle anchors are inconsistent")

    monkeypatch.setattr(
        runner,
        "_validate_file_backed_reservation_anchors",
        incomplete_claim,
    )

    with pytest.raises(
        runner.ContaminationError, match="claim anchors are not complete 111"
    ):
        runner._verify_single_run_state(_claimed_ticket())

    assert all(not path.exists() for path in paths.values())


def test_terminal_main_refuses_before_outcome_or_write(
    tmp_path, monkeypatch, capsys
):
    paths = _isolate_outputs(monkeypatch, tmp_path)
    terminal = _claimed_ticket()
    terminal.update(
        {
            "status": "rejected",
            "completed_at": "2099-01-01T00:00:00Z",
            "result": {"decision": "rejected"},
        }
    )
    paths["ticket"].write_text(json.dumps(terminal), encoding="utf-8")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("terminal rerun reached outcome or write path")

    monkeypatch.setattr(runner, "_verify_claim_bound_inputs", forbidden)
    monkeypatch.setattr(runner, "_read_exact_prices", forbidden)
    monkeypatch.setattr(runner, "_reserve_run_attempt", forbidden)
    monkeypatch.setattr(runner, "_write_json", forbidden)
    monkeypatch.setattr(runner, "persist_self_registered_result", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(RUNNER_PATH), "--warehouse-path", str(tmp_path / "unused.sqlite")],
    )

    assert runner.main() == 2
    message = json.loads(capsys.readouterr().err)
    assert message["status"] == "refused"
    assert message["trade_enabled"] is False
    assert not paths["raw"].exists()
    assert not paths["artifact"].exists()
    assert not paths["log"].exists()


def test_concurrent_attempts_admit_only_one_before_outcome(
    tmp_path, monkeypatch
):
    paths = _isolate_outputs(monkeypatch, tmp_path)
    ticket = _claimed_ticket()
    paths["ticket"].write_text(json.dumps(ticket), encoding="utf-8")
    monkeypatch.setattr(
        runner, "_validate_file_backed_reservation_anchors", lambda *_args: None
    )
    barrier = threading.Barrier(2)
    admitted = []
    refused = []
    outcome_reads = []
    lock = threading.Lock()

    def fake_verify_claim_bound_inputs(*_args):
        with lock:
            outcome_reads.append("claim_bound_inputs")
        return {}, {}, {}, {}

    def fake_read_exact_prices(*_args):
        with lock:
            outcome_reads.append("exact_prices")
        return {}

    monkeypatch.setattr(
        runner, "_verify_claim_bound_inputs", fake_verify_claim_bound_inputs
    )
    monkeypatch.setattr(runner, "_read_exact_prices", fake_read_exact_prices)

    def attempt(name):
        runner._verify_single_run_state(ticket)
        barrier.wait()
        try:
            handle = runner._reserve_run_attempt()
            claimed_ticket = runner._revalidate_reserved_run_state()
            runner._verify_claim_bound_inputs(claimed_ticket, tmp_path / "unused")
            runner._read_exact_prices(tmp_path / "unused", [])
            handle.close()
            with lock:
                admitted.append(name)
        except runner.ContaminationError:
            with lock:
                refused.append(name)

    threads = [threading.Thread(target=attempt, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(admitted) == 1
    assert len(refused) == 1
    assert outcome_reads == ["claim_bound_inputs", "exact_prices"]
    assert paths["raw"].exists()


def test_crashed_attempt_marker_remains_fail_closed(tmp_path, monkeypatch):
    paths = _isolate_outputs(monkeypatch, tmp_path)
    ticket = _claimed_ticket()
    anchor_calls = []

    def validate(*_args):
        anchor_calls.append("validated")

    monkeypatch.setattr(
        runner, "_validate_file_backed_reservation_anchors", validate
    )
    runner._verify_single_run_state(ticket)
    handle = runner._reserve_run_attempt()
    handle.close()

    with pytest.raises(runner.ContaminationError, match="already exists"):
        runner._verify_single_run_state(ticket)

    assert paths["raw"].read_bytes() == b""
    assert anchor_calls == ["validated"]


def test_json_outputs_are_create_only(tmp_path):
    path = tmp_path / "result.json"
    runner._write_json(path, {"attempt": 1})
    original = path.read_bytes()

    with pytest.raises(FileExistsError):
        runner._write_json(path, {"attempt": 2})

    assert path.read_bytes() == original
