"""exp-20260516-004: current-stack green momentum deceleration risk.

Retests the production-visible green momentum deceleration allocation state
from exp-20260513-023 on the current accepted core stack ending at
exp-20260515-028. This is a shadow risk-allocation scout only: it changes no
entry, exit, ranking, universe, LLM, or production-default behavior.
"""

from __future__ import annotations

import json
from typing import Any

import exp_20260513_023_green_momentum_deceleration_risk as prior


EXPERIMENT_ID = "exp-20260516-004"
EXPERIMENT_SLUG = "current_stack_green_momentum_deceleration_risk"
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075, 1.10]


def _refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["hypothesis"] = (
        "On the current accepted core stack, trend/breakout signals with "
        "accepted signal-day green confirmation and positive but decelerating "
        "10d-vs-20d momentum may deserve a smaller cap-aware allocation top-up "
        "than the prior rejected run, because this cohort can represent "
        "maturing trend continuation rather than fresh overextension."
    )
    payload["changed_variable"] = (
        "current_stack_green_momentum_deceleration_risk_multiplier"
    )
    payload["parameters"]["risk_multiplier_sweep"] = RISK_MULTIPLIER_SWEEP
    payload["gate_questions"]["2_history_check"] = {
        "exp-20260513-023": (
            "Same fixed state improved all three windows at 1.10x on the older "
            "stack, but failed because max drawdown worsened beyond the guardrail."
        ),
        "exp-20260513-013": (
            "The complementary green momentum acceleration state improved "
            "late/mid but regressed old_thin, so this run does not retry "
            "acceleration."
        ),
        "exp-20260515-028": (
            "Current accepted core stack now includes the confirmed-quality "
            "allocation layer, so this run retests the older positive-but-risky "
            "state with smaller multipliers."
        ),
        "blocked_branches_avoided": (
            "LLM soft-ranking and SEC semantics remain data-limited; Space "
            "source-diversity and benchmark-breadth slices are over-mined; "
            "generic candidate-pool expansion has recently added noise rather "
            "than stable EV."
        ),
    }
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe "
        "quant\\experiments\\exp_20260516_004_current_stack_green_momentum_deceleration_risk.py"
    )
    payload["related_files"] = [
        "quant/experiments/exp_20260516_004_current_stack_green_momentum_deceleration_risk.py",
        f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
        f"experiments/logs/{EXPERIMENT_ID}.json",
        f"experiments/tickets/{EXPERIMENT_ID}.json",
        f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
        "docs/experiment_log.jsonl",
    ]
    payload["why_not_other_changes"] = (
        "This run chose a fixed, production-visible core allocation state with "
        "prior positive but drawdown-limited evidence. It avoids LLM/SEC alpha "
        "because the required historical soft-ranking and directional filing "
        "fields are still insufficient, avoids Space/candidate breadth because "
        "recent canonical experiments show sample exhaustion or added noise, "
        "and avoids nearby accepted scalar retunes without a new discriminator."
    )
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
    }
    return payload


def main() -> dict[str, Any]:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP

    result = prior.run()
    result = _refresh_payload(result)
    prior._configure_persist()
    prior.base.persist(result)
    return result


if __name__ == "__main__":
    payload = main()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "selected_risk_multiplier": payload["parameters"][
                    "selected_risk_multiplier"
                ],
                "expected_value_score_delta": payload[
                    "expected_value_score_delta"
                ],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "improved_windows": payload["gate4"]["improved_windows"],
                "regressed_windows": payload["gate4"]["regressed_windows"],
                "adjusted_signal_count": payload["gate4"][
                    "adjusted_signal_count"
                ],
                "sweep_summary": payload["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
