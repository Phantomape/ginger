"""exp-20260515-028: current-stack core confirmed-quality risk.

Retests the production-visible confirmed-quality allocation state from
exp-20260513-018 on the current accepted core stack ending at exp-20260515-026.
The prior run improved EV/PnL but failed drawdown. This run changes only the
cap-aware post-sizing scalar sweep, using smaller values to see whether the
same fixed state now clears the canonical three-window gate.
"""

from __future__ import annotations

import json
from typing import Any

import exp_20260513_018_core_confirmed_quality_risk as prior


EXPERIMENT_ID = "exp-20260515-028"
EXPERIMENT_SLUG = "current_stack_core_confirmed_quality_risk"
RISK_MULTIPLIER_SWEEP = [1.025, 1.05, 1.06, 1.07, 1.075, 1.08, 1.09]


def _refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["hypothesis"] = (
        "The old confirmed-quality core state improved aggregate EV but failed "
        "drawdown on the 2026-05-13 stack. After the accepted cap-aware "
        "leader and price-vs-200MA allocation layers, the same fixed "
        "production-visible state may support a smaller incremental top-up "
        "without breaching drawdown."
    )
    payload["parameters"]["risk_multiplier_sweep"] = RISK_MULTIPLIER_SWEEP
    payload["gate_questions"]["2_history_check"] = {
        "exp-20260513-018": (
            "Same fixed state was rejected on the old stack: 1.08x+ improved "
            "all three windows but exceeded drawdown; 1.05-1.07x either "
            "regressed one window or did not clear Gate 4."
        ),
        "current_stack_context": (
            "Since then the accepted stack added clean-SPY cap releases, "
            "commodity/financial cap releases, broad price-vs-200MA extension, "
            "and trend-only price-vs-200MA extension. This is a current-stack "
            "retest, not a threshold change."
        ),
        "blocked_branches_avoided": (
            "LLM soft-ranking, SEC filing semantics, Space interactions, ETF "
            "candidate expansion, and nearby price-extension/cap retries are "
            "avoided because recent records mark them sample-limited or "
            "over-mined on the frozen windows."
        ),
    }
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe "
        "quant\\experiments\\exp_20260515_028_current_stack_core_confirmed_quality_risk.py"
    )
    payload["related_files"] = [
        "quant/experiments/exp_20260515_028_current_stack_core_confirmed_quality_risk.py",
        f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
        f"experiments/logs/{EXPERIMENT_ID}.json",
        f"experiments/tickets/{EXPERIMENT_ID}.json",
        f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
        "docs/experiment_log.jsonl",
    ]
    payload["why_not_other_changes"] = (
        "This run chose a production-visible core allocation state with prior "
        "positive but drawdown-limited evidence. It avoids LLM soft-ranking, "
        "Space slicing, SEC semantics, ETF/candidate-pool promotion, and "
        "nearby accepted price-extension or cap retunes because the latest "
        "experiment records show those branches are data-limited, over-mined, "
        "or recently rejected."
    )
    return payload


def main() -> dict[str, Any]:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP

    result = prior.run()
    result = _refresh_payload(result)
    prior.persist(result)
    return result


if __name__ == "__main__":
    payload = main()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "improved_windows": payload["gate4"]["improved_windows"],
                "regressed_windows": payload["gate4"]["regressed_windows"],
                "adjusted_signal_count": payload["gate4"]["adjusted_signal_count"],
                "selected_risk_multiplier": payload["parameters"][
                    "selected_risk_multiplier"
                ],
                "sweep_summary": payload["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
