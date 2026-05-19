"""exp-20260517-009: ample-slot stock rank-1 cap-aware top-up scout.

Tests one production-visible allocation discriminator after the rejected broad
ample-slot scout: when the shared entry planner has at least four available
slots, apply the top-up only to the already-selected rank-1 non-ETF,
non-Commodity core signal.

This is replay-only. A positive result must be promoted through shared
``production_parity.py`` policy plus parity tests before production behavior
changes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import exp_20260517_008_ample_slot_rank1_topup as prior


EXPERIMENT_ID = "exp-20260517-009"
EXPERIMENT_SLUG = "ample_slot_stock_rank1_topup"
MULTIPLIER_KEY = "ample_slot_stock_rank1_risk_multiplier_applied"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [1.0, 1.0125, 1.025, 1.05]
AVAILABLE_SLOTS_MIN = 4
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 2


def _apply_ample_slot_stock_topup(signals: list[dict[str, Any]], available_slots: int):
    if (
        available_slots < AVAILABLE_SLOTS_MIN
        or not signals
        or prior.CURRENT_RISK_MULTIPLIER <= 1.0
    ):
        return signals, []

    planned = list(signals)
    sig = dict(planned[0])
    sector = sig.get("sector")
    if not sector or sector in EXCLUDED_SECTORS:
        return signals, []

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
        or prior.production_parity_module.MAX_POSITION_PCT
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
    sizing["ample_slot_stock_rank1_state"] = True
    sizing["ample_slot_stock_rank1_available_slots"] = available_slots
    sizing["ample_slot_stock_rank1_baseline_shares"] = old_shares
    sizing["ample_slot_stock_rank1_desired_shares"] = desired_shares
    sizing["ample_slot_stock_rank1_cap_shares"] = cap_shares
    sizing["ample_slot_stock_rank1_new_shares"] = new_shares
    sizing[MULTIPLIER_KEY] = prior.CURRENT_RISK_MULTIPLIER
    sig["sizing"] = sizing
    planned[0] = sig

    adjustment = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sector,
        "available_slots": available_slots,
        "candidate_rank": 1,
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
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
        "signal_day_ticker_outperformed_spy": sig.get(
            "signal_day_ticker_outperformed_spy"
        ),
        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
    }
    prior.base.ADJUSTMENTS.append(adjustment)
    return planned, [adjustment]


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
    for label in prior.base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Ample-Slot Stock Rank-1 Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-selection top-up on the already-selected rank-1 signal when the shared entry planner has at least four available slots, excluding ETF and Commodity sectors. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.",
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
    prior.BASELINE_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    prior.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    prior.AVAILABLE_SLOTS_MIN = AVAILABLE_SLOTS_MIN
    prior.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    prior.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    prior.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    prior.CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    prior._apply_ample_slot_topup = _apply_ample_slot_stock_topup
    prior._markdown = _markdown


def _rewrite_payload(payload: dict[str, Any]) -> dict[str, Any]:
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_ample_slot_stock_rank1_topup"
    )
    interpretation = (
        "The non-ETF/non-Commodity ample-slot rank-1 top-up cleared the canonical three-window scout and requires shared production_parity promotion plus rerun before production use."
        if passed
        else "The non-ETF/non-Commodity ample-slot rank-1 top-up did not clear the canonical three-window gate."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "The broad ample-slot rank-1 scout failed because the old_thin "
                "Commodity row regressed while the stock rows remained mostly "
                "positive. Since Commodity and ETF exposure already has separate "
                "cap/risk policy, the next production-visible allocation state is "
                "an ample-slot rank-1 top-up restricted to non-ETF/non-Commodity "
                "core signals."
            ),
            "changed_variable": "ample_slot_stock_rank1_risk_multiplier",
            "single_causal_variable": (
                "post-selection cap-aware top-up on candidate_rank=1 when "
                "available_slots >= 4 and sector not in ETF/Commodities"
            ),
            "interpretation": interpretation,
            "rejection_reason": None if passed else interpretation,
            "next_evidence_needed": (
                None
                if passed
                else "Do not retry ample-slot top-ups without a materially different production-visible quality field or forward evidence."
            ),
            "anti_js": "No JavaScript was used.",
            "related_files": [
                "quant/experiments/exp_20260517_009_ample_slot_stock_rank1_topup.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"experiments/logs/{EXPERIMENT_ID}.json",
                f"experiments/tickets/{EXPERIMENT_ID}.json",
                f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["parameters"].update(
        {
            "state_definition": {
                "available_slots_min": AVAILABLE_SLOTS_MIN,
                "candidate_rank": 1,
                "already_selected_only": True,
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "cap_aware": True,
            },
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "capital allocation on a production-visible ample-slot stock rank-1 "
            "state; this keeps the candidate set fixed and uses a new sector "
            "discriminator rather than retrying the broad ample-slot rule"
        ),
        "2_history_check": {
            "exp-20260517-008": (
                "Broad available_slots >= 4 rank-1 top-up improved aggregate EV "
                "but failed because old_thin Commodity SLV regressed."
            ),
            "commodity_prior": (
                "Commodity trend/breakout exposure already has accepted dedicated "
                "cap and near-high rules, so excluding Commodity/ETF is a "
                "production-visible policy boundary rather than a ticker patch."
            ),
            "frozen_branches": (
                "Avoids LLM/SEC soft-ranking, nearby two-slot top-ups, and the "
                "sample-thin Financials DTE pocket."
            ),
        },
        "3_single_causal_variable": (
            "ample_slot_stock_rank1_risk_multiplier with fixed sector exclusion"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
            "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
            "at least six affected signals across at least two windows, and max drawdown "
            "drift <= 0.5 pp."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe "
            "quant\\experiments\\exp_20260517_009_ample_slot_stock_rank1_topup.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "production_parity plan_entry_candidates available_slots",
        "production_parity slot-sliced rank order",
        "risk_engine sector",
        "sizing shares_to_buy",
        "sizing entry_price",
        "sizing portfolio_value_usd",
        "sizing net_risk_per_share",
        "sizing max_position_pct_applied",
    ]
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the ample-slot stock top-up to shared "
                "production_parity.py used by both backtester.py and quant/run.py, "
                "add parity tests, and rerun all three canonical windows."
            ),
        }
    )
    payload["why_not_other_changes"] = (
        "LLM soft-ranking and SEC semantics remain field/coverage-limited; "
        "the Financials DTE pocket is sample-thin; two-slot and broad ample-slot "
        "top-ups failed. This tests one production-visible sector boundary on "
        "the same fixed candidate set."
    )
    payload["known_risks"] = [
        "The state is still a slot-availability allocation rule, so it should not be generalized to capacity or ranking.",
        "The old_thin window may stay unchanged because the stock-only state has no adjusted old_thin rows.",
        "A positive replay scout is not production-tradable until shared production_parity code and tests are promoted and rerun.",
    ]
    return payload


def main() -> dict[str, Any]:
    _configure_prior()
    result = prior.run()
    result = _rewrite_payload(result)
    prior.base.persist(result)
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
                "selected_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
