"""Shared detector for self-registering experiment runners.

Single source of truth for the no-self-registration guard, imported by the
pytest guard (`quant/test_no_new_self_registering_runners.py`), the audit CLI
(`experiment.py audit`), the allowlist refresh tool, and the pre-commit hook,
so the detection rule never drifts between them.

A runner "self-registers" when it writes `docs/experiment_registry.json` (or
ticket files) directly instead of going through `experiment.py new/close` or
`experiment_registry.persist_self_registered_result()`. That bypasses
`require_pre_run_prediction` and drops the prediction from the persisted record.

No JavaScript was used.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
ALLOWLIST_PATH = EXPERIMENTS_DIR / "_self_register_legacy_allowlist.txt"


def self_registers(text: str) -> bool:
    """True if the source mutates the registry experiments list or writes the
    registry file path directly.

    Mutating `registry["experiments"]` is the hard signal and always flags. A
    runner that delegates to `persist_self_registered_result()` (the sanctioned
    enforced+propagating path) is exempt -- it may reference the registry path to
    pass it to the helper and still write its own artifact files, which must not
    be mistaken for a direct registry write.
    """
    if 'setdefault("experiments"' in text or "setdefault('experiments'" in text:
        return True
    if "persist_self_registered_result(" in text:
        return False
    if "experiment_registry.json" in text and (
        "_write_json(" in text or "json.dump" in text or ".write_text(" in text
    ):
        return True
    return False


def current_offenders() -> set[str]:
    """File names of runners in quant/experiments that self-register."""
    offenders: set[str] = set()
    for path in sorted(EXPERIMENTS_DIR.glob("exp_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if self_registers(text):
            offenders.add(path.name)
    return offenders


def load_allowlist() -> set[str]:
    """Grandfathered legacy offenders (file names)."""
    if not ALLOWLIST_PATH.exists():
        return set()
    names: set[str] = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.add(line)
    return names


def new_offenders() -> list[str]:
    """Sorted offenders not grandfathered by the allowlist."""
    return sorted(current_offenders() - load_allowlist())


def staged_new_offenders() -> list[str]:
    """Staged (added/modified) runner files that newly self-register.

    Scoped to the commit so a pre-commit hook blocks only the offending agent,
    not everyone. Returns [] on any git error (fail-open).
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    allow = load_allowlist()
    flagged: list[str] = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        path = REPO_ROOT / rel
        name = path.name
        if path.parent != EXPERIMENTS_DIR or not name.startswith("exp_"):
            continue
        if name in allow:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if self_registers(text):
            flagged.append(name)
    return sorted(flagged)


def _main(argv=None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Self-registration guard. Exit 1 only on a confirmed new "
        "offender (so a pre-commit hook can fail-open on tooling errors)."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check only staged files (pre-commit scope) instead of the whole tree.",
    )
    args = parser.parse_args(argv)
    offenders = staged_new_offenders() if args.staged else new_offenders()
    if offenders:
        scope = "staged" if args.staged else "repo"
        sys.stderr.write(
            f"BLOCKED: new self-registering experiment runner(s) [{scope}]:\n  "
            + "\n  ".join(offenders)
            + "\nThese write docs/experiment_registry.json directly, bypassing "
            "prediction enforcement. Use `experiment.py new`/`close` or "
            "`experiment_registry.persist_self_registered_result()`. See "
            "docs/agent_experiment_protocol.md (Hard No).\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
