"""exp-20260520-037: payment-network Financials core risk scout.

Alpha search. Tests one current-pool governance variable: whether the existing
core long stack over-allocates to payment-network Financials (V/MA), which are
not bank/brokerage-style Financials even when classified in the same sector.

Entries, exits, ranking, universe, slots, heat, LLM/news, and all non-target
sizing rules stay fixed. This is replay-only unless a future promotion adds a
shared production/backtest policy and reruns the canonical three windows.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import exp_20260516_039_tsm_core_adaptation as prior


EXPERIMENT_ID = "exp-20260520-037"
EXPERIMENT_SLUG = "payment_network_financials_risk"
MULTIPLIER_KEY = "payment_network_financials_risk_multiplier_applied"
TARGET_TICKERS = {"V", "MA"}
TARGET_STRATEGIES = {"trend_long", "breakout_long"}
MIN_AFFECTED_SIGNAL_COUNT = 4
MIN_AFFECTED_WINDOW_COUNT = 2
BASELINE_ARTIFACT = (
    f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json#before_metrics"
)
TRIAL_ACCOUNTING = {
    "trial_family": "current_ticker_pool_governance",
    "changed_variable": "payment_network_financials_risk_multiplier",
    "prior_trial_count": 4,
    "nearby_prior_experiments": [
        "exp-20260516-039",
        "exp-20260516-042",
        "exp-20260518-022",
        "exp-20260520-035",
    ],
    "multiple_testing_risk_bucket": "high",
    "new_evidence_type": "canonical_current_stack_three_window_contribution",
}


def _target_signal(sig: dict[str, Any]) -> bool:
    return (
        str(sig.get("ticker") or "").upper() in TARGET_TICKERS
        and sig.get("strategy") in TARGET_STRATEGIES
    )


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    new_shares = int(math.floor(shares * scalar))
    if new_shares >= shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    position_value = entry * new_shares
    risk_amount = net_risk_per_share * new_shares
    out = dict(sizing)
    out["payment_network_financials_baseline_shares"] = shares
    out["payment_network_financials_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _build_lifecycle_diagnostic(
    before_runs: dict[str, dict[str, Any]],
    identity_candidates: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    trades: list[dict[str, Any]] = []
    for label, run in before_runs.items():
        rows_by_ticker = {
            ticker: prior._load_ohlcv_rows(prior.WINDOWS[label]["snapshot"], ticker)
            for ticker in TARGET_TICKERS
        }
        for trade in run["trades"]:
            ticker = str(trade.get("ticker") or "").upper()
            if ticker in TARGET_TICKERS:
                trades.append(prior._diagnose_trade(label, trade, rows_by_ticker[ticker]))

    horizon_summary: dict[str, Any] = {}
    for horizon in prior.HORIZONS:
        key = f"{horizon}d_net_return_pct"
        values = [
            trade.get("horizon_returns", {}).get(key)
            for trade in trades
            if isinstance(trade.get("horizon_returns", {}).get(key), (int, float))
        ]
        horizon_summary[key] = {
            "count": len(values),
            "positive_count": sum(1 for value in values if value > 0),
            "avg_net_return_pct": round(sum(values) / len(values), 6)
            if values
            else None,
            "min_net_return_pct": min(values) if values else None,
            "max_net_return_pct": max(values) if values else None,
        }

    fast_candidates = [
        trade for trade in trades if trade.get("fast_target_candidate_before_exit")
    ]
    return {
        "status": "observed_only",
        "target_tickers": sorted(TARGET_TICKERS),
        "trade_count": len(trades),
        "win_count": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0),
        "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "horizon_summary": horizon_summary,
        "profit_available_before_exit_count": sum(
            1 for trade in trades if trade.get("profit_available_before_exit")
        ),
        "fast_target_candidate_count": len(fast_candidates),
        "fast_target_supported": len(fast_candidates) >= 2,
        "branch_recommendation": (
            "run_fast_target_rescue"
            if len(fast_candidates) >= 2
            else "prioritize_risk_governance"
        ),
        "candidate_signals_by_window": identity_candidates,
        "trades": trades,
    }


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {wins} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                passed=(
                    "PASS"
                    if row["passed"]
                    else ("CTRL" if row["is_identity_control"] else "FAIL")
                ),
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                wins=row["affected_window_count"],
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Payment-Network Financials Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier for already-qualified core long signals whose ticker is `V` or `MA`.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
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
            "Production impact: replay-only. Any positive promotion would need shared constants/portfolio-engine implementation, parity tests, and another canonical three-window run.",
            "",
            "No JavaScript was used.",
        ]
    )


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.TARGET_TICKER = "PAYMENT_NETWORK_FINANCIALS"
    prior.TARGET_STRATEGIES = TARGET_STRATEGIES
    prior.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    prior.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    prior._target_signal = _target_signal
    prior._scale_sizing = _scale_sizing
    prior._build_lifecycle_diagnostic = _build_lifecycle_diagnostic
    prior._markdown = _markdown


def build_payload() -> dict[str, Any]:
    _configure_prior()
    payload = prior.run()
    payload["gate1"]["baseline_artifact"] = BASELINE_ARTIFACT
    payload["gate1"]["baseline_note"] = (
        "Current accepted codebase measured in this run before applying the "
        "payment-network Financials replay scalar."
    )
    payload.update(TRIAL_ACCOUNTING)
    payload["status"] = (
        "accepted_for_shared_policy_implementation"
        if payload["gate4"]["passed"]
        else "rejected_payment_network_financials_risk"
    )
    payload["decision"] = payload["status"]
    payload["hypothesis"] = (
        "Payment-network Financials (V/MA) may not deserve the same medium-term "
        "core long risk treatment as bank/brokerage Financials. A bounded "
        "post-sizing haircut can test whether this current ticker-pool cohort is "
        "a repeat drag without changing entries, ranking, exits, or LLM/news."
    )
    payload["change_type"] = "risk_allocation_shadow"
    payload["changed_variable"] = "payment_network_financials_risk_multiplier"
    payload["single_causal_variable"] = (
        "post-sizing risk scalar for existing core long signals where ticker in {V, MA}"
    )
    payload["parameters"].update(
        {
            "target_tickers": sorted(TARGET_TICKERS),
            "target_strategies": sorted(TARGET_STRATEGIES),
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "risk allocation / current ticker-pool governance: payment-network "
            "Financials may be overfit by Financials sector-leader boosts."
        ),
        "2_history_check": {
            "current_baseline_diagnostic": (
                "V had two current-stack losses in one canonical window; MA is "
                "in the universe but did not execute in the selected baseline."
            ),
            "accepted_ticker_specific_work": (
                "TSM and ISRG scalar work exists, so this run is high "
                "multiple-testing risk and requires a strict sample guard."
            ),
            "anti_repeat": (
                "This is not retained unless it clears cross-window sample "
                "guards; a one-window V improvement is explicitly insufficient."
            ),
        },
        "3_single_causal_variable": "payment_network_financials_risk_multiplier",
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three fixed windows; aggregate EV/PnL "
            "positive, >=2 improved windows, no EV-regressed windows, survival "
            ">=5%, affected signals >=4 across >=2 windows, and drawdown drift <=0.5pp."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260520_037_payment_network_financials_risk.py"
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "promotion_requirement": (
            "If accepted, add a shared payment-network Financials risk policy "
            "used by both backtester.py and run.py, add attribution/parity tests, "
            "then rerun all three canonical windows."
        ),
    }
    payload["why_not_other_changes"] = (
        "LLM soft-ranking and SEC semantic branches are data-limited; state-surface "
        "and broad-market scalar/profile retunes are under anti-repeat guidance; "
        "current-pool governance is the direct alpha lane, but this cohort must "
        "clear strict cross-window sample evidence."
    )
    payload["known_risks"] = [
        "The target cohort may collapse to V-only in the canonical windows.",
        "Ticker-pool governance is high multiple-testing risk after TSM/ISRG work.",
        "A positive fixed-window result cannot be promoted without shared policy and parity tests.",
    ]
    if payload["gate4"]["passed"]:
        payload["interpretation"] = (
            "Payment-network Financials cleared the replay gate, but promotion "
            "still needs shared policy/parity implementation."
        )
        payload["rejection_reason"] = None
    else:
        payload["interpretation"] = (
            "Payment-network Financials did not clear Gate 4; the cohort remains "
            "too sample-thin for production policy."
        )
        payload["rejection_reason"] = payload["interpretation"]
    payload["next_evidence_needed"] = (
        "Need broader forward/current-stack payment-network outcomes or a true "
        "business-model field before retrying this cohort."
    )
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        "quant/experiments/exp_20260520_037_payment_network_financials_risk.py",
        f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
        f"experiments/logs/{EXPERIMENT_ID}.json",
        f"experiments/tickets/{EXPERIMENT_ID}.json",
        f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
        "docs/experiment_log.jsonl",
    ]
    return payload


def main() -> None:
    payload = build_payload()
    prior.base._markdown = _markdown
    prior.base.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "selected_risk_multiplier": payload["parameters"][
                    "selected_risk_multiplier"
                ],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "improved_windows": payload["gate4"]["improved_windows"],
                "regressed_windows": payload["gate4"]["regressed_windows"],
                "adjusted_signal_count": payload["gate4"]["adjusted_signal_count"],
                "affected_window_count": payload["gate4"]["affected_window_count"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
