from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from quant.experiments import exp_20260505_025_post_addon_deterioration_loss_taxonomy as audit


audit.EXPERIMENT_ID = "exp-20260505-028"
audit.OUTPUT = Path(
    "data/experiments/exp-20260505-028/"
    "exp_20260505_028_post_addon_deterioration_loss_taxonomy.json"
)


if __name__ == "__main__":
    audit.main()
