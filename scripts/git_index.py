"""Small, strict helpers for reading the Git index rather than the worktree."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitIndexError(RuntimeError):
    """Raised when a staged-content guard cannot inspect the Git index."""


def _run_git(repo_root: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise GitIndexError(f"cannot execute git: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitIndexError(
            f"git {' '.join(args)} failed with exit {proc.returncode}: {detail}"
        )
    return proc.stdout


def staged_paths(repo_root: Path, *, diff_filter: str = "ACMR") -> list[str]:
    """Return repo-relative staged paths exactly as represented by the index."""
    raw = _run_git(
        repo_root,
        "diff",
        "--cached",
        "--name-only",
        f"--diff-filter={diff_filter}",
        "-z",
    )
    try:
        return [part.decode("utf-8") for part in raw.split(b"\0") if part]
    except UnicodeDecodeError as exc:
        raise GitIndexError(f"staged path is not valid UTF-8: {exc}") from exc


def index_bytes(repo_root: Path, relative_path: str) -> bytes:
    """Read one file from the index (stage 0), never from the worktree."""
    return _run_git(repo_root, "show", f":{relative_path}")


def index_text(repo_root: Path, relative_path: str) -> str:
    """Read one UTF-8 text file from the index, failing closed on bad bytes."""
    raw = index_bytes(repo_root, relative_path)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitIndexError(
            f"staged {relative_path} is not valid UTF-8: {exc}"
        ) from exc
