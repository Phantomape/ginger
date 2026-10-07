"""Cross-lane reservation tests use disposable real Git worktrees."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_registry as registry
from experiment_lane_identity import collect_lane_experiment_id_sources, git_common_dir
import stale_artifact_sweep


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Identity test",
         "-c", "user.email=identity@example.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def lanes(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "primary")
    _git(root, "commit", "--allow-empty", "-m", "fixture")
    sibling = tmp_path / "sibling lane"
    _git(root, "worktree", "add", "-b", "sibling", str(sibling))
    return root, sibling


def _proposal(name):
    return {
        "lane": "measurement_repair", "hypothesis": f"Repair identity {name}.",
        "change_type": "identity_or_measurement_repair",
        "single_causal_variable": f"identity {name}",
        "allowed_write_scope": ["scripts/experiment_registry.py"],
        "baseline_result_file": "data/fixture.json",
    }


def _reserve(root, name="test", **kwargs):
    return registry.reserve_experiment(root / "docs/experiment_registry.json",
                                       **_proposal(name), **kwargs)


def _write(root, relative, text="{}"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_live_sibling_paths_are_consumed_without_reading_payloads(lanes, monkeypatch):
    root, sibling = lanes
    identity = "exp-20990101-009"
    ticket = _write(sibling, f"experiments/tickets/{identity}.json", "not JSON")
    _write(sibling, "quant/experiments/exp_20990101_010_probe.py")
    (sibling / "data/experiments/exp-20990101-011").mkdir(parents=True)
    original_read = Path.open

    def forbid_payload_read(path, *args, **kwargs):
        if sibling in path.parents:
            raise AssertionError("cross-lane payload read")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", forbid_payload_read)
    sources = registry.collect_experiment_id_sources(root=root)
    assert identity in sources
    assert any(source.startswith("worktree:") for source in sources[identity])
    assert registry.next_experiment_id({}, today="20990101", root=root) == "exp-20990101-012"
    monkeypatch.undo()
    assert ticket.read_bytes() == b"not JSON"


def test_ref_only_identity_blocks_explicit_and_automatic_reservation(lanes):
    root, sibling = lanes
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    identity = f"exp-{today}-007"
    _git(root, "checkout", "-b", "history-only")
    ticket = _write(root, f"experiments/tickets/{identity}.json", "historical bytes")
    _git(root, "add", "experiments")
    _git(root, "commit", "-m", "historical identity")
    _git(root, "checkout", "primary")
    assert not ticket.exists()
    sources = registry.collect_experiment_id_sources(root=sibling)
    assert any(source.startswith("ref:refs/heads/history-only:") for source in sources[identity])
    with pytest.raises(ValueError, match="already exists"):
        _reserve(sibling, experiment_id=identity)
    reserved = _reserve(sibling)
    assert reserved["experiment_id"] == f"exp-{today}-008"
    assert _git(root, "show", f"history-only:experiments/tickets/{identity}.json") == "historical bytes"


def test_new_ref_tip_is_not_hidden_by_tree_cache(lanes):
    root, _ = lanes
    assert "exp-20990101-020" not in collect_lane_experiment_id_sources(root)
    _write(root, "experiments/tickets/exp-20990101-020.json")
    _git(root, "add", "experiments")
    _git(root, "commit", "-m", "new identity")
    sources = collect_lane_experiment_id_sources(root)
    assert any(source.startswith("ref:refs/heads/primary:")
               for source in sources["exp-20990101-020"])


def test_detached_worktree_head_keeps_a_locally_deleted_identity(lanes):
    root, sibling = lanes
    _git(sibling, "checkout", "--detach")
    ticket = _write(sibling, "experiments/tickets/exp-20990101-030.json")
    _git(sibling, "add", "experiments")
    _git(sibling, "commit", "-m", "detached identity")
    ticket.unlink()
    sources = collect_lane_experiment_id_sources(root)
    assert any(source.startswith("worktree_head:")
               for source in sources["exp-20990101-030"])


_WORKER = """
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import experiment_registry as registry
root, ready, start = map(Path, sys.argv[2:5])
original = registry.next_experiment_id
def delayed(*args, **kwargs):
    identity = original(*args, **kwargs)
    time.sleep(0.4)  # widen the original cross-worktree allocation race
    return identity
registry.next_experiment_id = delayed
ready.touch()
while not start.exists():
    time.sleep(0.01)
ticket = registry.reserve_experiment(
    root / 'docs/experiment_registry.json',
    lane='measurement_repair', hypothesis='Repair identity ' + root.name,
    change_type='identity_or_measurement_repair', single_causal_variable=root.name,
    allowed_write_scope=['scripts/experiment_registry.py'],
    baseline_result_file='data/fixture.json',
)
print(json.dumps({'id': ticket['experiment_id'], 'uid': ticket['experiment_uid']}))
"""


def test_concurrent_processes_in_two_worktrees_get_distinct_durable_ids(lanes, tmp_path):
    root, sibling = lanes
    assert git_common_dir(root) == git_common_dir(sibling)
    start = tmp_path / "start"
    ready = [tmp_path / f"ready-{i}" for i in range(2)]
    processes = [subprocess.Popen(
        [sys.executable, "-B", "-c", _WORKER, str(SCRIPTS), str(lane), str(marker), str(start)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ) for lane, marker in zip(lanes, ready)]
    try:
        deadline = time.monotonic() + 20
        while not all(path.exists() for path in ready):
            assert time.monotonic() < deadline, "reservation worker did not start"
            time.sleep(0.01)
        start.touch()
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            results.append(json.loads(stdout))
        assert len({result["id"] for result in results}) == 2
        assert len({result["uid"] for result in results}) == 2
        for lane, result in zip(lanes, results):
            ticket = lane / f"experiments/tickets/{result['id']}.json"
            assert json.loads(ticket.read_text())["experiment_uid"] == result["uid"]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()


def test_idempotent_retry_and_cache_refresh_outside_common_lock(lanes, monkeypatch):
    root, _ = lanes
    calls = []

    def cache_update(path, ticket, timeout):
        with registry.file_lock(git_common_dir(root) / "experiment_id_allocation", timeout_seconds=0):
            calls.append(ticket["experiment_uid"])

    monkeypatch.setattr(registry, "_best_effort_cache_upsert", cache_update)
    first = _reserve(root)
    second = _reserve(root)
    assert first["experiment_id"] == second["experiment_id"]
    assert calls == [first["experiment_uid"], first["experiment_uid"]]


def test_non_git_fixture_under_real_repository_stays_local(lanes):
    root, sibling = lanes
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    _write(sibling, f"experiments/tickets/exp-{today}-050.json")
    fixture = root / "nested_fixture"
    fixture.mkdir()
    assert git_common_dir(fixture) is None
    assert collect_lane_experiment_id_sources(fixture) == {}
    ticket = _reserve(fixture)
    assert ticket["experiment_id"] == f"exp-{today}-001"


@pytest.mark.parametrize("payload", [
    {"released_at": "2026-09-06T00:00:00Z"}, {"pid": 12345}, {},
])
@pytest.mark.parametrize("dry_run", [False, True])
def test_sweep_keeps_persistent_allocation_anchor_only(tmp_path, monkeypatch, payload, dry_run):
    monkeypatch.setattr(stale_artifact_sweep, "_pid_alive", lambda pid: False)
    anchor = _write(tmp_path, ".git/experiment_id_allocation.lock", json.dumps(payload))
    residue = [
        _write(tmp_path, ".git/index.lock"),
        _write(tmp_path, ".git/worktrees/other/experiment_id_allocation.lock"),
        _write(tmp_path, "docs/experiment_id_allocation.lock"),
        _write(tmp_path, "docs/ordinary.lock", json.dumps({"released_at": "done"})),
        _write(tmp_path, "docs/.orphan.tmp"),
    ]
    for path in [anchor, *residue]:
        os.utime(path, (0, 0))
    original = anchor.read_bytes()
    result = stale_artifact_sweep.sweep_stale_artifacts(
        tmp_path, now=3600, lock_max_age_s=1, tmp_max_age_s=1, dry_run=dry_run,
    )
    assert anchor.read_bytes() == original
    assert result["kept_count"] == 1
    assert {row["path"] for row in result["removed"]} == {str(path) for path in residue}
    assert all(path.exists() == dry_run for path in residue)
