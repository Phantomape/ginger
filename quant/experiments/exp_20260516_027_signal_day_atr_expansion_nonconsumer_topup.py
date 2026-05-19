"""exp-20260516-027: non-consumer signal-day ATR expansion top-up.

The broad ATR-expansion top-up in exp-20260516-026 improved late_strong and
mid_weak but regressed old_thin. The regression was concentrated in the same
Consumer Discretionary / Communication Services area that the accepted
green-deceleration quality top-up already excludes.

This experiment keeps the ATR-expansion state and top-up mechanism fixed, but
narrows the production-visible state by excluding Consumer Discretionary and
Communication Services from both the percentile universe and the eligible
signals. It is a replay scout only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import exp_20260516_026_signal_day_atr_expansion_topup as broad


EXPERIMENT_ID = "exp-20260516-027"
EXPERIMENT_SLUG = "signal_day_atr_expansion_nonconsumer_topup"
MULTIPLIER_KEY = "signal_day_atr_expansion_nonconsumer_topup_multiplier_applied"
EXCLUDED_SECTORS = {
    "ETF",
    "Commodities",
    "Consumer Discretionary",
    "Communication Services",
}


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                windows=", ".join(row["affected_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in broad.scout.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Non-Consumer Signal-Day ATR Expansion Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout signals whose signal-day `atr_expansion` is in the same-day top quartile after excluding ETF, Commodities, Consumer Discretionary, and Communication Services. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected non-control multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-expansion state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_broad_module() -> None:
    broad.EXPERIMENT_ID = EXPERIMENT_ID
    broad.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    broad.MULTIPLIER_KEY = MULTIPLIER_KEY
    broad.scout.EXPERIMENT_ID = EXPERIMENT_ID
    broad.scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    broad.scout.MULTIPLIER_KEY = MULTIPLIER_KEY
    broad.scout.EXCLUDED_SECTORS = EXCLUDED_SECTORS
    broad.scout._markdown = _markdown
    broad._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_broad_module()
    payload = broad.run()
    selected = payload["parameters"]["selected_risk_multiplier"]
    passed = payload["gate4"]["passed"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": (
                "accepted_for_shared_policy_implementation"
                if passed
                else "rejected_signal_day_atr_expansion_nonconsumer_topup"
            ),
            "decision": (
                "accepted_for_shared_policy_implementation"
                if passed
                else "rejected_signal_day_atr_expansion_nonconsumer_topup"
            ),
            "hypothesis": (
                "ATR expansion behaved like a positive breakout-strength state in "
                "exp-20260516-026, but the broad top-up regressed old_thin through "
                "Consumer Discretionary and Communication Services exposure. "
                "Excluding those sectors should preserve the late/mid alpha while "
                "removing the weak-window drag."
            ),
            "changed_variable": (
                "signal_day_atr_expansion_nonconsumer_topup_multiplier"
            ),
            "single_causal_variable": (
                "cap-aware post-sizing top-up multiplier for signal-day top-quartile "
                "ATR expansion trend/breakout signals outside ETF, Commodities, "
                "Consumer Discretionary, and Communication Services"
            ),
            "interpretation": (
                "Non-consumer signal-day ATR expansion top-up cleared the canonical three-window scout and requires shared risk/portfolio promotion plus rerun before production use."
                if passed
                else "Non-consumer signal-day ATR expansion top-up did not clear the canonical three-window gate."
            ),
            "rejection_reason": None
            if passed
            else "Non-consumer signal-day ATR expansion top-up did not clear the canonical three-window gate.",
            "next_evidence_needed": None
            if passed
            else "Do not retry nearby non-consumer ATR-expansion top-up scalars without forward hold-quality evidence or a different production-visible discriminator.",
            "related_files": [
                "quant/experiments/exp_20260516_027_signal_day_atr_expansion_nonconsumer_topup.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"experiments/logs/{EXPERIMENT_ID}.json",
                f"experiments/tickets/{EXPERIMENT_ID}.json",
                f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["parameters"]["state_definition"] = {
        "feature": "atr_expansion",
        "cutoff": (
            "same-day top quartile after excluding ETF, Commodities, "
            "Consumer Discretionary, and Communication Services"
        ),
        "top_fraction": broad.scout.TOP_FRACTION,
        "strategies": sorted(broad.scout.STATE_STRATEGIES),
        "excluded_sectors": sorted(EXCLUDED_SECTORS),
    }
    payload["parameters"]["selected_risk_multiplier"] = selected
    payload["gate_questions"]["1_alpha_hypothesis"] = (
        "risk allocation on a production-visible non-consumer ATR expansion "
        "strength state; this follows the playbook preference for fixed "
        "candidate-set allocation and uses the broad top-up failure to narrow "
        "the state rather than expanding the candidate pool"
    )
    payload["gate_questions"]["2_history_check"] = {
        "exp-20260516-026": (
            "Broad ATR-expansion top-up improved late_strong and mid_weak but "
            "regressed old_thin, with drag concentrated in Consumer "
            "Discretionary / Communication Services."
        ),
        "exp-20260516-009": (
            "Accepted green-deceleration quality top-up already excludes "
            "Consumer Discretionary and Communication Services, making this "
            "sector exclusion a prior-supported production-visible discriminator."
        ),
        "llm_and_candidate_pool": (
            "LLM soft-ranking/SEC fields remain attribution-limited, and recent "
            "candidate-pool additions added noise or old-window regression."
        ),
    }
    payload["gate_questions"]["3_single_causal_variable"] = (
        "signal_day_atr_expansion_nonconsumer_topup_multiplier with fixed "
        "sector-excluded top-quartile state"
    )
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe "
        "quant\\experiments\\exp_20260516_027_signal_day_atr_expansion_nonconsumer_topup.py"
    )
    payload["production_impact"]["promotion_requirement"] = (
        "If accepted, add the non-consumer ATR-expansion state and sizing key in "
        "shared risk_engine.py/portfolio_engine.py paths used by both "
        "backtester.py and run.py, then rerun all three canonical windows."
    )
    payload["why_not_other_changes"] = (
        "This follows the evidence from the rejected broad ATR-expansion top-up "
        "instead of moving to LLM/SEC branches with sparse attribution, Space "
        "peer-state retries with zero incremental EV/PnL, or noisy candidate-pool "
        "expansion."
    )
    payload["anti_js"] = "No JavaScript was used."
    return payload


def main() -> dict[str, Any]:
    result = run()
    broad.scout.base.persist(result)
    return result


if __name__ == "__main__":
    result = main()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "affected_windows": result["gate4"]["affected_windows"],
                "selected_risk_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
