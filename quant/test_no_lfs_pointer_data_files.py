"""Guard: strategy data surfaces must never contain unsmudged git-LFS pointers.

On 2026-06-05 a git operation left 51 LFS pointer files in the worktree under
``data/non_ohlcv``; loaders crashed or silently read partial data and the SEC
FTD+FINRA sleeve was dead for six days (exp-20260611-027). ``.gitattributes``
now reserves LFS for oversized files only, and this test fails fast if any
pointer text reappears on the surfaces production code reads directly.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LFS_HEADER = b"version https://git-lfs"

# Directories whose files production/replay code opens directly as data.
GUARDED_DIRS = [
    REPO_ROOT / "data" / "non_ohlcv",
    REPO_ROOT / "data" / "paper_sleeves",
    REPO_ROOT / "data" / "ledgers",
    REPO_ROOT / "data" / "state",
    REPO_ROOT / "data" / "reference",
]
GUARDED_FILES = [
    REPO_ROOT / "docs" / "experiment_log.jsonl",
]

# LFS pointer files are ~130 bytes; anything bigger cannot be a pointer.
MAX_POINTER_SIZE = 400


def _pointer_files() -> list[Path]:
    hits: list[Path] = []
    candidates: list[Path] = [p for p in GUARDED_FILES if p.exists()]
    for root in GUARDED_DIRS:
        if not root.is_dir():
            continue
        candidates.extend(p for p in root.rglob("*") if p.is_file())
    for path in candidates:
        try:
            if path.stat().st_size > MAX_POINTER_SIZE:
                continue
            with path.open("rb") as handle:
                head = handle.read(len(LFS_HEADER))
        except OSError:
            continue
        if head == LFS_HEADER:
            hits.append(path)
    return hits


def test_no_unsmudged_lfs_pointers_on_data_surfaces():
    hits = _pointer_files()
    assert not hits, (
        "Unsmudged git-LFS pointer files found on data surfaces; restore them "
        "from .git/lfs/objects (or git lfs checkout) before relying on any "
        "sleeve/forward evidence: " + ", ".join(str(p) for p in hits)
    )
