from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from alpha_playbook_guard import (  # noqa: E402
    PLAYBOOK_REL,
    audit_playbook_text,
    audit_repository_contract,
    audit_staged_contract,
)
import experiment as experiment_cli  # noqa: E402


PLAYBOOK_PATH = REPO_ROOT / PLAYBOOK_REL


def _codes(report: dict) -> set[str]:
    return {row["code"] for row in report["violations"]}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _init_contract_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    playbook = repo / PLAYBOOK_REL
    playbook.parent.mkdir(parents=True)
    valid_text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    playbook.write_text(valid_text, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", PLAYBOOK_REL)
    _git(
        repo,
        "-c",
        "user.name=Playbook Guard Test",
        "-c",
        "user.email=playbook-guard@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "seed valid playbook",
    )
    return repo, playbook, valid_text


def test_alpha_playbook_repository_contract_passes() -> None:
    report = audit_repository_contract(REPO_ROOT)
    assert report["passed"], report["violations"]


def test_validator_returns_stable_codes_for_malformed_structure() -> None:
    valid = PLAYBOOK_PATH.read_text(encoding="utf-8")
    malformed = valid.replace("## Frozen Zones", "## Trial Chronicle", 1)
    report = audit_playbook_text(malformed)
    assert report["passed"] is False
    assert "h2_sequence_changed" in _codes(report)


def test_experiment_ids_are_restricted_to_durable_priors() -> None:
    valid = PLAYBOOK_PATH.read_text(encoding="utf-8")
    malformed = valid.replace(
        "<!-- PLAYBOOK_END -->",
        "A recent result was `exp-20260719-999`.\n\n<!-- PLAYBOOK_END -->",
    )
    report = audit_playbook_text(malformed)
    assert "experiment_reference_outside_priors" in _codes(report)


def test_staged_guard_reads_invalid_index_not_fixed_worktree(tmp_path: Path) -> None:
    repo, playbook, valid = _init_contract_repo(tmp_path)
    playbook.write_text(valid + "\nappended trial result\n", encoding="utf-8")
    _git(repo, "add", PLAYBOOK_REL)
    playbook.write_text(valid, encoding="utf-8")

    report = audit_staged_contract(repo)
    assert report["passed"] is False
    assert "end_sentinel_failed" in _codes(report)


def test_staged_guard_ignores_invalid_unstaged_worktree(tmp_path: Path) -> None:
    repo, playbook, valid = _init_contract_repo(tmp_path)
    valid_index = valid.replace(
        "This document is a durable decision map",
        "This document remains a durable decision map",
        1,
    )
    playbook.write_text(valid_index, encoding="utf-8")
    _git(repo, "add", PLAYBOOK_REL)
    playbook.write_text(valid_index + "\nunstaged trial result\n", encoding="utf-8")

    report = audit_staged_contract(repo)
    assert report["passed"] is True, report["violations"]


def test_staged_runner_may_not_depend_on_playbook(tmp_path: Path) -> None:
    repo, _, _ = _init_contract_repo(tmp_path)
    runner_rel = "quant/experiments/exp_20260719_999_bad.py"
    runner = repo / runner_rel
    runner.parent.mkdir(parents=True)
    runner.write_text(
        'PLAYBOOK = "docs/alpha-optimization-playbook.md"\n', encoding="utf-8"
    )
    _git(repo, "add", runner_rel)

    report = audit_staged_contract(repo)
    assert report["passed"] is False
    assert "staged_runner_depends_on_playbook" in _codes(report)


def test_lean_strict_blocks_playbook_failure_without_relabeling_quality(
    monkeypatch,
) -> None:
    emitted: list[dict] = []
    monkeypatch.setattr(experiment_cli, "load_registry", lambda _path: {})
    monkeypatch.setattr(
        experiment_cli,
        "audit_experiment_process",
        lambda *_args, **_kwargs: {
            "passed": True,
            "lean_quality_passed": True,
            "post_enforcement_alpha_ticket_count": 1,
            "legacy_pre_enforcement_alpha_ticket_count": 0,
        },
    )
    monkeypatch.setattr(experiment_cli, "_self_register_new_offenders", lambda: [])
    monkeypatch.setattr(
        experiment_cli,
        "_audit_alpha_playbook",
        lambda: {
            "passed": False,
            "violations": [{"code": "line_budget_exceeded"}],
        },
    )
    monkeypatch.setattr(experiment_cli, "print_json", emitted.append)

    with pytest.raises(SystemExit) as exc_info:
        experiment_cli._audit(["--lean-strict"])

    assert exc_info.value.code == 2
    assert emitted[0]["lean_quality_passed"] is True
    assert emitted[0]["lean_strict_passed"] is False
    assert emitted[0]["lean_strict_would_block"] is True
    assert emitted[0]["lean_strict_failure_domains"] == [
        "alpha_playbook_contract"
    ]
