"""exp-20260427-017 gap-down recovery universe scout rerun.

This wrapper reruns the exp-20260427-013 shadow audit under a fresh experiment
id because the generated exp-20260427-013 closeout log path was already occupied
by another agent's historical log. It still performs observed-only evaluation.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "quant" / "experiments" / (
    "exp_20260427_013_liquidity_qualified_gap_down_recovery_shadow_candidate_definition.py"
)
EXPERIMENT_ID = "exp-20260427-017"


def _load_source_module():
    spec = importlib.util.spec_from_file_location("exp_20260427_013_gap_down_source", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load source module: {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_source_module()
    module.EXPERIMENT_ID = EXPERIMENT_ID
    module.OUT_JSON = os.path.join(
        str(REPO_ROOT),
        "data",
        "experiments",
        EXPERIMENT_ID,
        "exp_20260427_017_gap_down_recovery_shadow.json",
    )
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
