"""Shared paths for files the operator edits by hand."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPERATOR_INPUTS_DIR = REPO_ROOT / "operator_inputs"
LEGACY_DATA_DIR = REPO_ROOT / "data"

OPEN_POSITIONS_FILENAME = "open_positions.json"

OPEN_POSITIONS_PATH = OPERATOR_INPUTS_DIR / OPEN_POSITIONS_FILENAME

LEGACY_OPEN_POSITIONS_PATH = LEGACY_DATA_DIR / OPEN_POSITIONS_FILENAME


def _resolve_input_path(path: str | Path | None, primary: Path, legacy: Path) -> Path:
    if path is not None:
        requested = Path(path)
        candidates = [requested]
        if not requested.is_absolute():
            candidates.append(REPO_ROOT / requested)
            candidates.append((Path(__file__).resolve().parent / requested).resolve())
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return requested
    if primary.exists():
        return primary
    if legacy.exists():
        return legacy
    return primary


def open_positions_path(path: str | Path | None = None) -> Path:
    """Return the open positions path, preferring operator_inputs/."""
    return _resolve_input_path(path, OPEN_POSITIONS_PATH, LEGACY_OPEN_POSITIONS_PATH)


def repo_relative(path: str | Path) -> str:
    """Display a path relative to the repo when possible."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)
