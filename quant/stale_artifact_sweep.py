"""Sweep stale orphaned ``.tmp`` / ``.lock`` residue left by hard-killed
concurrent experiment and git operations.

Atomic writes (temp + ``os.replace``) and file locks clean up after themselves
via ``try/finally``, but a *hard* process kill (timeout, OOM, concurrency abort,
crashed git subprocess) bypasses ``finally`` and leaks either a
``.<name>.<rand>.tmp`` or a still-present ``.lock``. Nothing else removes these,
so they accumulate; a stale ``.git/index.lock`` / ``experiment_registry.json.lock``
can block *all* commits and registry writes for hours (observed: a 77-minute
stale ``index.lock`` stalled the whole repo).

This sweep removes only residue that is provably abandoned:

* ``.tmp`` older than ``tmp_max_age_s`` (no live atomic write lasts minutes);
* ``.lock`` that is either an experiment lock JSON with ``released_at`` set / a
  dead owner ``pid``, or simply older than ``lock_max_age_s``.

Live operations are protected by the age thresholds (real writes/locks complete
in milliseconds-to-seconds). Read-only and idempotent; safe to call at the start
of any experiment/run flow.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TMP_MAX_AGE_S = 300.0      # 5 min: orphan atomic-write temp
# 30 min: abandoned lock. Conservative because this age threshold is the ONLY
# gate for git's own .lock files (which are not the experiment-lock JSON format,
# so _lock_is_dead can't read a pid/released_at from them) -- a long-running git
# gc/repack must not have its lock yanked. Experiment locks (registry/log/ticket)
# are JSON with pid+released_at, so they're cleaned promptly via _lock_is_dead
# regardless of this age, and are unaffected by the longer window.
DEFAULT_LOCK_MAX_AGE_S = 1800.0

# Directories that accumulate experiment residue (scanned one level; os.scandir
# is used rather than Path.glob so dot-prefixed temp files are matched).
_RESIDUE_DIRS = (
    "experiments/tickets",
    "experiments/logs",
    "experiments/manifests",
    "experiments/cards",
    "docs",
)


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness check. Unknown -> assume alive (conservative)."""
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
            )
            if not handle:
                return False
            exit_code = ctypes.c_ulong(0)
            ok = ctypes.windll.kernel32.GetExitCodeProcess(
                handle, ctypes.byref(exit_code)
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            STILL_ACTIVE = 259
            return bool(ok) and exit_code.value == STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


def _lock_is_dead(path: Path) -> bool:
    """True if an experiment lock file records a released/dead owner."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("released_at"):
        return True
    pid = data.get("pid")
    if isinstance(pid, int) and not _pid_alive(pid):
        return True
    return False


def _iter_residue(repo_root: Path):
    for rel in _RESIDUE_DIRS:
        directory = repo_root / rel
        if directory.is_dir():
            for entry in os.scandir(directory):
                if entry.is_file() and entry.name.endswith((".tmp", ".lock")):
                    yield Path(entry.path)
    data_experiments = repo_root / "data" / "experiments"
    if data_experiments.is_dir():
        for sub in os.scandir(data_experiments):
            if not sub.is_dir():
                continue
            for entry in os.scandir(sub.path):
                if entry.is_file() and entry.name.endswith((".tmp", ".lock")):
                    yield Path(entry.path)
    git_dir = repo_root / ".git"
    if git_dir.is_dir():
        for root, _dirs, files in os.walk(git_dir):
            for name in files:
                if name.endswith(".lock"):
                    yield Path(root) / name


def sweep_stale_artifacts(
    repo_root: Path | str = REPO_ROOT,
    *,
    now: float | None = None,
    tmp_max_age_s: float = DEFAULT_TMP_MAX_AGE_S,
    lock_max_age_s: float = DEFAULT_LOCK_MAX_AGE_S,
    dry_run: bool = False,
) -> dict:
    """Remove stale ``.tmp`` / ``.lock`` residue. Returns a summary dict."""
    repo_root = Path(repo_root)
    now = time.time() if now is None else now
    removed: list[dict] = []
    kept = 0
    for path in _iter_residue(repo_root):
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if path.name.endswith(".lock"):
            stale = _lock_is_dead(path) or age > lock_max_age_s
        else:
            stale = age > tmp_max_age_s
        if not stale:
            kept += 1
            continue
        if not dry_run:
            try:
                path.unlink()
            except OSError:
                continue
        removed.append({"path": str(path), "age_s": round(age)})
    return {
        "removed_count": len(removed),
        "kept_count": kept,
        "removed": removed,
        "dry_run": dry_run,
    }


def sweep_quietly(repo_root: Path | str = REPO_ROOT) -> int:
    """Best-effort sweep that never raises. Returns count removed (0 on error).

    Intended for opportunistic calls at the start of experiment/run flows."""
    try:
        return sweep_stale_artifacts(repo_root)["removed_count"]
    except Exception:
        return 0


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--tmp-max-age-s", type=float, default=DEFAULT_TMP_MAX_AGE_S)
    parser.add_argument("--lock-max-age-s", type=float, default=DEFAULT_LOCK_MAX_AGE_S)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = sweep_stale_artifacts(
        args.repo_root,
        tmp_max_age_s=args.tmp_max_age_s,
        lock_max_age_s=args.lock_max_age_s,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
