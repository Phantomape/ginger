"""Tests for the derived monolithic experiment log.

``docs/experiment_log.jsonl`` is an untracked, derived view rebuilt from the
per-experiment shards (``experiments/logs/*.json``) via
``experiment.py rebuild-log``. These tests pin two properties:

1. ``rebuild_experiment_log_from_shards`` is deterministic and faithful to the
   shards (one sorted line per shard) -- so parallel agents/clones regenerate a
   byte-identical file and never produce divergent-append merge conflicts.
2. The active canonical log writers do not append to the monolithic file
   directly (that direct-write is what caused the merge conflicts this change
   retired).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    rebuild_experiment_log_from_shards,
    save_experiment_log_entry,
)


def _write_shard(logs_dir: Path, exp_id: str, **extra) -> None:
    row = {"experiment_id": exp_id, "status": "rejected", **extra}
    save_experiment_log_entry(row, logs_dir=logs_dir)


def test_rebuild_is_sorted_one_line_per_shard(tmp_path):
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    log_path = tmp_path / "docs" / "experiment_log.jsonl"
    log_path.parent.mkdir(parents=True)

    # Deliberately out of order on disk.
    _write_shard(logs_dir, "exp-20260624-001", decision="b")
    _write_shard(logs_dir, "exp-20260623-002", decision="a")
    _write_shard(logs_dir, "exp-20260623-029", decision="c")

    n = rebuild_experiment_log_from_shards(logs_dir=logs_dir, log_path=log_path)
    assert n == 3

    lines = log_path.read_text(encoding="utf-8").splitlines()
    ids = [json.loads(ln)["experiment_id"] for ln in lines]
    assert ids == [
        "exp-20260623-002",
        "exp-20260623-029",
        "exp-20260624-001",
    ]


def test_rebuild_is_deterministic_and_idempotent(tmp_path):
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    log_path = tmp_path / "docs" / "experiment_log.jsonl"
    log_path.parent.mkdir(parents=True)

    _write_shard(logs_dir, "exp-20260623-002", decision="a", nested={"k": 1})
    _write_shard(logs_dir, "exp-20260623-029", decision="c")

    rebuild_experiment_log_from_shards(logs_dir=logs_dir, log_path=log_path)
    first = log_path.read_bytes()
    rebuild_experiment_log_from_shards(logs_dir=logs_dir, log_path=log_path)
    second = log_path.read_bytes()
    assert first == second  # byte-identical re-run -> no merge conflicts


def test_rebuild_empty_logs_dir(tmp_path):
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    log_path = tmp_path / "docs" / "experiment_log.jsonl"
    log_path.parent.mkdir(parents=True)
    n = rebuild_experiment_log_from_shards(logs_dir=logs_dir, log_path=log_path)
    assert n == 0
    assert log_path.read_text(encoding="utf-8") == ""


def test_active_writers_do_not_write_monolithic_log():
    """The canonical log writers persist shards, not the monolithic file.

    These writers have no legitimate reason to name ``experiment_log.jsonl``
    outside a comment anymore: they write the per-experiment shard, and the
    monolithic file is rebuilt from shards. We forbid *any* non-comment mention
    of the path so variable-based appends (``p = .../experiment_log.jsonl``;
    ``p.open("a")`` on a later line) cannot slip through a same-line heuristic.
    """
    offenders = []
    for rel in [
        "scripts/run_free_short_pressure_shadow_experiment.py",
        "scripts/run_short_interest_shadow_experiment.py",
        "scripts/append_experiment_log.py",
        "scripts/audit_sector_state_alpha.py",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue  # explanatory comments may name the path
            if "experiment_log.jsonl" in line:
                offenders.append(f"{rel}:{lineno}: {stripped}")
    assert not offenders, (
        "non-comment monolithic-log reference found (write shards instead):\n"
        + "\n".join(offenders)
    )
