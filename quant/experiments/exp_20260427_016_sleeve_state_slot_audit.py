"""Observed-only sleeve/state slot audit wrapper for exp-20260427-016."""

from __future__ import annotations

from pathlib import Path

import exp_20260427_011_sleeve_state_slot_audit as audit


audit.EXPERIMENT_ID = "exp-20260427-016"
audit.OUTPUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "experiments"
    / audit.EXPERIMENT_ID
    / "exp_20260427_016_sleeve_state_slot_audit.json"
)


if __name__ == "__main__":
    audit.main()
