"""Maintain the legacy self-registration allowlist (strict-A workflow).

The guard test ``quant/test_no_new_self_registering_runners.py`` fails when a
NON-grandfathered runner writes ``docs/experiment_registry.json`` directly. The
allowlist freezes the known legacy offenders so only NEW leaks fail.

This tool keeps that allowlist honest under the strict policy:

- It always PRUNES entries for runners that no longer self-register (migrated to
  ``experiment.py new/close`` or ``persist_self_registered_result()``, or
  deleted). Pruning is safe and keeps the allowlist shrinking.
- It REFUSES to silently grandfather NEW offenders. If new direct-registry
  writers appeared, it lists them and exits non-zero so you migrate them. Pass
  ``--accept-new`` only when you deliberately decide to grandfather them.
- ``--check`` reports the diff without writing (use in review).

The detector is imported from the guard test so the two never drift.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "_self_register_guard",
    QUANT_DIR / "test_no_new_self_registering_runners.py",
)
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)

ALLOWLIST_PATH = _guard.ALLOWLIST_PATH
HEADER = (
    "# Legacy self-registering experiment runners (grandfathered).\n"
    "# These predate the no-self-registration guard. Do NOT add new entries:\n"
    "# new runners must use experiment.py new/close or\n"
    "# experiment_registry.persist_self_registered_result(). See\n"
    "# quant/test_no_new_self_registering_runners.py.\n"
)


def _write_allowlist(names: list[str]) -> None:
    ALLOWLIST_PATH.write_text(HEADER + "\n".join(sorted(names)) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report the diff without writing; exit non-zero if changes are needed.",
    )
    parser.add_argument(
        "--accept-new",
        action="store_true",
        help="Deliberately grandfather any NEW offenders into the allowlist.",
    )
    args = parser.parse_args()

    current = _guard._current_offenders()
    allow = _guard._load_allowlist()
    new_offenders = sorted(current - allow)
    migrated = sorted(allow - current)

    print(f"current self-registering runners: {len(current)}")
    print(f"allowlisted: {len(allow)}")
    if migrated:
        print(f"to prune (no longer self-register): {len(migrated)}")
        for name in migrated:
            print(f"  - {name}")
    if new_offenders:
        print(f"NEW offenders (not grandfathered): {len(new_offenders)}")
        for name in new_offenders:
            print(f"  + {name}")

    if not migrated and not new_offenders:
        print("allowlist already in sync; nothing to do.")
        return 0

    if new_offenders and not args.accept_new:
        print(
            "\nRefusing to grandfather new offenders. Migrate them to "
            "experiment.py new/close or persist_self_registered_result(), or "
            "rerun with --accept-new to deliberately grandfather them.",
            file=sys.stderr,
        )
        return 2

    # New allowlist: drop migrated; include new offenders only when accepted.
    kept = (allow - set(migrated)) | (set(new_offenders) if args.accept_new else set())
    # Always reflect reality for kept entries that still self-register.
    kept = {name for name in kept if name in current}

    if args.check:
        print("\n--check: changes needed (not written).")
        return 1

    _write_allowlist(sorted(kept))
    print(f"\nwrote {ALLOWLIST_PATH} with {len(kept)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
