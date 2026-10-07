"""Read experiment identities across Git lanes without reading result payloads."""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path


_ID_RE = re.compile(r"(?<![A-Za-z0-9])exp[-_](\d{8})[-_](\d{3,})(?!\d)", re.I)
_PATH_ROOTS = ("experiments", "docs/experiments", "data/experiments", "quant/experiments")
_LIVE_DIRS = (
    "experiments/tickets", "experiments/logs", "experiments/manifests",
    "experiments/cards", "experiments/artifacts", "docs/experiments/tickets",
    "docs/experiments/logs", "data/experiments",
)


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
        text=True, encoding="utf-8", errors="surrogateescape", timeout=60,
    ).stdout


def git_common_dir(root):
    """Return the common Git directory only for an exact worktree root.

    In particular, test fixtures below a real checkout remain local registries.
    A broken Git checkout fails closed rather than silently allocating locally.
    """
    root = Path(root).resolve()
    if not (root / ".git").exists():
        return None
    top = Path(_git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    if top != root:
        return None
    common = Path(_git(root, "rev-parse", "--git-common-dir").strip())
    return (root / common).resolve()


def _id_paths(paths):
    # One representative path per ID is sufficient to prove occupancy.
    found = {}
    for path in paths:
        for match in _ID_RE.finditer(path):
            identity = f"exp-{match[1]}-{int(match[2]):03d}"
            found.setdefault(identity, path)
    return tuple(sorted(found.items()))


@lru_cache(maxsize=64)
def _tree_id_paths(common, sha):
    # Tree names only: never cat-file/show an experiment's result JSON.
    paths = _git(common, "ls-tree", "-r", "-t", "--name-only", "-z", sha,
                 "--", *_PATH_ROOTS).split("\0")
    return _id_paths(paths)


def _live_id_paths(root):
    paths = []
    for relative in _LIVE_DIRS:
        directory = root / relative
        if directory.is_dir():
            paths.extend(path.relative_to(root).as_posix() for path in directory.iterdir())
    runners = root / "quant/experiments"
    if runners.is_dir():
        paths.extend(path.relative_to(root).as_posix() for path in runners.rglob("exp*"))
    return _id_paths(paths)


def collect_lane_experiment_id_sources(root):
    """Union ref-tip and sibling worktree path identities, including untracked IDs.

    Occupancy is conservative and independent of lifecycle status or outcomes.
    Old IDs/UIDs are never rewritten, reconciled, or imported into this lane.
    """
    root = Path(root).resolve()
    common = git_common_dir(root)
    if common is None:
        return {}
    sources = {}

    def remember(pairs, source):
        for identity, path in pairs:
            sources.setdefault(identity, set()).add(f"{source}:{path}")

    refs = _git(root, "for-each-ref", "--format=%(refname) %(objectname) %(objecttype) %(*objectname) %(*objecttype)")
    for line in refs.splitlines():
        fields = line.split()
        ref, sha, kind = fields[:3]
        if kind == "tag" and len(fields) == 5:
            sha, kind = fields[3:]
        if kind in {"commit", "tree"}:
            remember(_tree_id_paths(str(common), sha), f"ref:{ref}")

    sibling = None
    for field in _git(root, "worktree", "list", "--porcelain", "-z").split("\0"):
        if field.startswith("worktree "):
            sibling = Path(field.removeprefix("worktree ")).resolve()
            if sibling != root and sibling.is_dir():
                remember(_live_id_paths(sibling), f"worktree:{sibling.as_posix()}")
        elif field.startswith("HEAD ") and sibling is not None:
            sha = field.removeprefix("HEAD ")
            if sha.strip("0"):
                remember(_tree_id_paths(str(common), sha), f"worktree_head:{sibling.as_posix()}")
    return sources
