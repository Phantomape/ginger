"""exp-20260517-006: two-slot rank-2 cap-aware top-up scout.

This tests a different two-slot allocation mechanism from exp-20260517-005.
Instead of front-loading the already selected rank-1 signal when two slots
remain, it asks whether the marginal second selected signal deserves a small
cap-aware post-sizing top-up. Entries, filters, ranking, exits, targets,
universe, LLM/news, heat, and all existing sizing rules stay fixed.
"""

from __future__ import annotations

import json
import math
from typing import Any

import exp_20260517_005_two_slot_rank1_topup as prior
import exp_20260512_106_signal_day_sector_tape_risk as base
import production_parity as production_parity_module


EXPERIMENT_ID = "exp-20260517-006"
EXPERIMENT_SLUG = "two_slot_rank2_topup"
MULTIPLIER_KEY = "two_slot_rank2_risk_multiplier_applied"


def _apply_two_slot_rank2_topup(
    signals: list[dict[str, Any]],
    available_slots: int,
):
    if (
        available_slots != 2
        or len(signals or []) < 2
        or prior.CURRENT_RISK_MULTIPLIER <= 1.0
    ):
        return signals, []

    planned = list(signals)
    sig = dict(planned[1])
    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return signals, []

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or portfolio_value <= 0 or net_risk_per_share <= 0:
        return signals, []

    cap_pct = float(
        sizing.get("max_position_pct_applied")
        or production_parity_module.MAX_POSITION_PCT
    )
    desired_shares = max(
        old_shares,
        int(math.floor(old_shares * prior.CURRENT_RISK_MULTIPLIER)),
    )
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= old_shares:
        return signals, []

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value
    sizing["two_slot_rank2_state"] = True
    sizing["two_slot_rank2_available_slots"] = available_slots
    sizing["two_slot_rank2_baseline_shares"] = old_shares
    sizing["two_slot_rank2_desired_shares"] = desired_shares
    sizing["two_slot_rank2_cap_shares"] = cap_shares
    sizing["two_slot_rank2_new_shares"] = new_shares
    sizing[MULTIPLIER_KEY] = prior.CURRENT_RISK_MULTIPLIER
    sig["sizing"] = sizing
    planned[1] = sig

    adjustment = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector", "Unknown"),
        "available_slots": available_slots,
        "candidate_rank": 2,
        "baseline_shares": old_shares,
        "desired_shares": desired_shares,
        "cap_shares": cap_shares,
        "new_shares": new_shares,
        "multiplier": prior.CURRENT_RISK_MULTIPLIER,
        "trade_quality_score": sig.get("trade_quality_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "regime_exit_score": sig.get("regime_exit_score"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "signal_day_ticker_green_candle": sig.get(
            "signal_day_ticker_green_candle"
        ),
        "signal_day_ticker_outperformed_spy": sig.get(
            "signal_day_ticker_outperformed_spy"
        ),
        "price_vs_200ma_extension_state": sig.get(
            "price_vs_200ma_extension_state"
        ),
    }
    base.ADJUSTMENTS.append(adjustment)
    return planned, [adjustment]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.3f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
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
    for label in base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Two-Slot Rank-2 Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware risk top-up on the already-selected rank-2 signal when `available_slots == 2`. The accepted one-slot rank-1 top-up remains unchanged in both baseline and variants. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must implement this in shared `production_parity.py`, add parity tests, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior._apply_two_slot_topup = _apply_two_slot_rank2_topup
    prior._markdown = _markdown


def _retitle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_two_slot_rank2_topup"
    )
    interpretation = (
        "The two-slot rank-2 top-up cleared the canonical three-window scout and requires shared production_parity promotion plus rerun before production use."
        if passed
        else "The marginal rank-2 signal in two-slot entry plans did not clear Gate 4 on the frozen three-window evidence."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "The failed two-slot rank-1 top-up may have front-loaded heat into "
                "the first selected signal. If the two-slot state contains useful "
                "marginal capacity, a small cap-aware top-up on the already-selected "
                "rank-2 signal can improve EV without changing entries or ranking."
            ),
            "changed_variable": "two_slot_rank2_risk_multiplier",
            "single_causal_variable": (
                "post-selection cap-aware top-up on candidate_rank=2 when available_slots == 2"
            ),
            "interpretation": interpretation,
            "rejection_reason": None if passed else interpretation,
            "next_evidence_needed": (
                None
                if passed
                else "Do not broaden two-slot scarce-capital top-ups on these windows without a materially different production-visible discriminator."
            ),
            "related_files": [
                "quant/experiments/exp_20260517_006_two_slot_rank2_topup.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"docs/experiments/logs/{EXPERIMENT_ID}.json",
                f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
                f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["parameters"]["state_definition"]["candidate_rank"] = 2
    payload["parameters"]["locked_variables"] = [
        "core universe",
        "entry filters",
        "candidate ranking",
        "candidate pool",
        "stop and target logic",
        "all existing sizing multipliers",
        "one-slot rank-1 top-up",
        "portfolio heat",
        "LLM/news replay",
        "event sleeves",
    ]
    payload["gate_questions"]["1_alpha_hypothesis"] = (
        "capital allocation on a production-visible slot-state extension; "
        "this follows the playbook preference for fixed-candidate allocation "
        "and avoids LLM/SEC soft-ranking data limits"
    )
    payload["gate_questions"]["2_history_check"] = {
        "exp-20260517-004": (
            "Accepted available_slots == 1 rank-1 cap-aware top-up at 1.075."
        ),
        "exp-20260517-005": (
            "Rejected available_slots == 2 rank-1 top-up because late_strong "
            "regressed and sample count was thin; this tests the marginal rank-2 "
            "slot instead of front-loading rank 1."
        ),
        "llm_and_candidate_pool": (
            "LLM/SEC soft-ranking remains attribution-limited and recent "
            "candidate-pool expansion added noise or old-window regression."
        ),
    }
    payload["gate_questions"]["3_single_causal_variable"] = (
        "two_slot_rank2_risk_multiplier applied only after shared candidate "
        "selection when available_slots == 2"
    )
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe "
        "quant\\experiments\\exp_20260517_006_two_slot_rank2_topup.py"
    )
    payload["production_impact"]["promotion_requirement"] = (
        "If accepted, add the two-slot rank-2 top-up to shared production_parity.py "
        "used by both backtester.py and quant/run.py, add parity tests, and rerun "
        "all three canonical windows."
    )
    payload["why_not_other_changes"] = (
        "This avoids LLM/SEC branches because PIT semantic attribution is still "
        "insufficient, avoids Space/event-sleeve retunes because recent variants "
        "are already documented and default-off, avoids nearby rank-1 two-slot "
        "retry after exp-20260517-005 failed, and avoids candidate-pool expansion "
        "because recent breadth additions added noise."
    )
    payload["known_risks"] = [
        "The state is adjacent to the rejected two-slot rank-1 scout and must be rejected if any window regresses.",
        "A rank-2 top-up can still consume heat before later fills and add marginal-slot fragility.",
        "A positive replay scout is not production-tradable until shared production_parity code and tests are promoted and rerun.",
    ]
    return payload


def run() -> dict[str, Any]:
    _configure_prior()
    return _retitle_payload(prior.run())


def main() -> dict[str, Any]:
    result = run()
    base.persist(result)
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
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
