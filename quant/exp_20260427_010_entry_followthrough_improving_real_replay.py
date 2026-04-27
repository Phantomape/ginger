"""Canonical entry point for exp-20260427-010.

The implementation file could not be renamed in-place on this Windows
workspace, so this wrapper preserves the experiment id in the runnable path.
"""

from __future__ import annotations

import importlib


def main() -> int:
    module = importlib.import_module(
        "exp_20260427_009_entry_followthrough_improving_real_replay"
    )
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
