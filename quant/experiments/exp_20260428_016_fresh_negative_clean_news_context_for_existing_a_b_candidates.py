"""exp-20260428-016 wrapper for fresh negative clean-news context audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260428_012_fresh_t1_negative_clean_news_context_for_existing_a_b_candidates.py"
)

spec = importlib.util.spec_from_file_location("exp_20260428_012_negative_news", SOURCE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

module.EXPERIMENT_ID = "exp-20260428-016"
module.OUT_DIR = REPO_ROOT / "data" / "experiments" / module.EXPERIMENT_ID
module.OUT_JSON = module.OUT_DIR / (
    "exp_20260428_016_fresh_negative_clean_news_context_for_existing_a_b_candidates.json"
)


if __name__ == "__main__":
    result = module.run_experiment()
    result["experiment_id"] = module.EXPERIMENT_ID
    result["single_causal_variable"] = (
        "fresh negative clean-news context for existing A/B candidates"
    )
    module.OUT_JSON.write_text(
        module.json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
