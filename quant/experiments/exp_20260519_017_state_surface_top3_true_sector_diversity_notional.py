"""exp-20260519-017: state-surface top-3 true-sector diversity notional.

Alpha search. Re-runs the residual top-3 sector-diversity allocation scout
from exp-20260519-016 with one corrected production-visible input: sectors are
read from the shared risk_engine.SECTOR_MAP ticker map instead of the replay row
sector field.

No JavaScript is used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
for search_path in (REPO_ROOT, QUANT_ROOT):
    text = str(search_path)
    if text not in sys.path:
        sys.path.insert(0, text)

import exp_20260519_016_state_surface_top3_sector_diversity_notional as base
from risk_engine import SECTOR_MAP


EXPERIMENT_ID = "exp-20260519-017"
EXPERIMENT_SLUG = "state_surface_top3_true_sector_diversity_notional"
RULE_VERSION = "state_surface_top3_true_sector_diversity_rank_notional_v1"


def _true_sector(trade: dict[str, Any]) -> str:
    ticker = str(trade.get("ticker") or "").upper()
    return str(SECTOR_MAP.get(ticker) or "Unknown")


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.RULE_VERSION = RULE_VERSION
    base.OUT_JSON = (
        base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    )
    base.LOG_JSON = base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    base.TICKET_JSON = (
        base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    base.ARTIFACT_MD = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    base.__file__ = str(Path(__file__).resolve())
    base._sector = _true_sector


def main() -> None:
    _configure_base_module()
    base.main()


if __name__ == "__main__":
    main()
