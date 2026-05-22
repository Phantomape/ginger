"""exp-20260522-023: breakout Communication Services dual-haircut risk scout.

Alpha search. The current core stack already applies two independent 0.25x
risk tags to some Communication Services breakout signals:
`breakout_comms_gap_risk_multiplier_applied` and
`breakout_comms_near_high_risk_multiplier_applied`.

This experiment changes one variable only: a replay-only post-sizing scalar
for already-qualified core breakout signals that have both tags. It does not
change signal generation, ranking, exits, universe, LLM/news, or production
orders. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import exp_20260516_039_tsm_core_adaptation as prior


EXPERIMENT_ID = "exp-20260522-023"
EXPERIMENT_SLUG = "breakout_comms_dual_haircut_risk"
MULTIPLIER_KEY = "breakout_comms_dual_haircut_risk_multiplier_applied"
DUAL_KEYS = (
    "breakout_comms_gap_risk_multiplier_applied",
    "breakout_comms_near_high_risk_multiplier_applied",
)
TARGET_SECTOR = "Communication Services"
TARGET_STRATEGY = "breakout_long"
MIN_AFFECTED_SIGNAL_COUNT = 4
MIN_AFFECTED_WINDOW_COUNT = 2
BASELINE_ARTIFACT = (
    f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json#before_metrics"
)
TRIAL_ACCOUNTING = {
    "trial_family": "current_stack_existing_haircut_residual_risk",
    "changed_variable": "breakout_comms_dual_haircut_risk_multiplier",
    "prior_trial_count": 5,
    "nearby_prior_experiments": [
        "exp-20260505-012",
        "exp-20260516-020",
        "exp-20260520-037",
        "exp-20260520-038",
        "exp-20260520-041",
    ],
    "multiple_testing_risk_bucket": "high",
    "new_evidence_type": "canonical_current_stack_three_window_multiplier_attribution",
}


def _dual_comms_signal(sig: dict[str, Any]) -> bool:
    sizing = sig.get("sizing") or {}
    return (
        sig.get("strategy") == TARGET_STRATEGY
        and sig.get("sector") == TARGET_SECTOR
        and all(float(sizing.get(key) or 0.0) == 0.25 for key in DUAL_KEYS)
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
    out["breakout_comms_dual_haircut_baseline_shares"] = shares
    out["breakout_comms_dual_haircut_new_shares"] = new_shares
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
    candidate_count_by_window = {
        label: len(rows) for label, rows in identity_candidates.items()
    }
    for label, run in before_runs.items():
        for trade in run["trades"]:
            multipliers = trade.get("sizing_multipliers") or {}
            if (
                trade.get("strategy") == TARGET_STRATEGY
                and trade.get("sector") == TARGET_SECTOR
                and all(float(multipliers.get(key) or 0.0) == 0.25 for key in DUAL_KEYS)
            ):
                trades.append(
                    {
                        "window": label,
                        "ticker": trade.get("ticker"),
                        "entry_date": trade.get("entry_date"),
                        "exit_date": trade.get("exit_date"),
                        "exit_reason": trade.get("exit_reason"),
                        "pnl": round(float(trade.get("pnl") or 0.0), 2),
                        "pnl_pct_net": trade.get("pnl_pct_net"),
                        "sizing_multipliers": multipliers,
                    }
                )

    by_window: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "pnl": 0.0, "wins": 0}
    )
    by_ticker: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "pnl": 0.0, "wins": 0, "windows": set()}
    )
    for trade in trades:
        pnl = float(trade["pnl"])
        window = str(trade["window"])
        ticker = str(trade["ticker"])
        by_window[window]["trade_count"] += 1
        by_window[window]["pnl"] = round(by_window[window]["pnl"] + pnl, 2)
        by_window[window]["wins"] += 1 if pnl > 0 else 0
        by_ticker[ticker]["trade_count"] += 1
        by_ticker[ticker]["pnl"] = round(by_ticker[ticker]["pnl"] + pnl, 2)
        by_ticker[ticker]["wins"] += 1 if pnl > 0 else 0
        by_ticker[ticker]["windows"].add(window)
    for row in by_ticker.values():
        row["windows"] = sorted(row["windows"])

    total_pnl = round(sum(float(trade["pnl"]) for trade in trades), 2)
    return {
        "status": "observed_only",
        "target_sector": TARGET_SECTOR,
        "target_strategy": TARGET_STRATEGY,
        "required_existing_risk_tags": list(DUAL_KEYS),
        "candidate_count_by_window": candidate_count_by_window,
        "candidate_count": sum(candidate_count_by_window.values()),
        "trade_count": len(trades),
        "win_count": sum(1 for trade in trades if float(trade["pnl"]) > 0),
        "total_pnl": total_pnl,
        "by_window": dict(sorted(by_window.items())),
        "by_ticker": dict(sorted(by_ticker.items())),
        "trades": trades,
        "branch_recommendation": "risk_governance_scout",
        "fast_target_supported": False,
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
                passed="PASS"
                if row["passed"]
                else ("CTRL" if row["is_identity_control"] else "FAIL"),
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
            f"# {EXPERIMENT_ID} Breakout Communication Services Dual-Haircut Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier for already-qualified Communication Services breakout signals that have both accepted 0.25x risk tags.",
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
            "Production impact: replay-only. Any positive promotion would need shared portfolio-engine implementation, run.py parity, and a fresh canonical rerun.",
            "",
            "No JavaScript was used.",
        ]
    )


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.TARGET_TICKER = "BREAKOUT_COMMS_DUAL_HAIRCUT"
    prior.TARGET_STRATEGIES = {TARGET_STRATEGY}
    prior.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    prior.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    prior._target_signal = _dual_comms_signal
    prior._scale_sizing = _scale_sizing
    prior._build_lifecycle_diagnostic = _build_lifecycle_diagnostic
    prior._markdown = _markdown


def build_payload() -> dict[str, Any]:
    _configure_prior()
    payload = prior.run()
    payload.update(TRIAL_ACCOUNTING)
    payload["status"] = (
        "accepted_for_shared_policy_implementation"
        if payload["gate4"]["passed"]
        else "rejected_breakout_comms_dual_haircut_risk"
    )
    payload["decision"] = payload["status"]
    payload["hypothesis"] = (
        "Communication Services breakout signals that already require both "
        "gap and near-high 0.25x haircuts may still have poor replacement value. "
        "A bounded post-sizing scalar tests whether existing risk evidence should "
        "be compressed further without adding a new filter or ticker."
    )
    payload["change_type"] = "risk_allocation_shadow"
    payload["changed_variable"] = "breakout_comms_dual_haircut_risk_multiplier"
    payload["single_causal_variable"] = (
        "post-sizing risk scalar for already-qualified Communication Services "
        "breakout signals with both existing 0.25x risk tags"
    )
    payload["parameters"].update(
        {
            "target_sector": TARGET_SECTOR,
            "target_strategy": TARGET_STRATEGY,
            "required_existing_risk_tags": list(DUAL_KEYS),
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "risk allocation: a signal already hit by both Communication Services "
            "breakout haircuts may still be over-allocated versus its realized value."
        ),
        "2_history_check": {
            "exp-20260505-012": (
                "Compound severe-haircut no-trade was rejected; this run tests "
                "one named production-visible dual-risk family instead of a broad count."
            ),
            "exp-20260520-038/041": (
                "DTE residual and non-confirming candle scalars were rejected; "
                "this run does not touch DTE or candle filters."
            ),
            "current_multiplier_attribution": (
                "The current three-window core stack shows the dual Communication "
                "Services breakout tag has negative executed PnL, but sample risk is high."
            ),
        },
        "3_single_causal_variable": payload["single_causal_variable"],
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three fixed windows; positive aggregate "
            "EV/PnL, >=2 improved windows, no EV-regressed windows, drawdown drift "
            "<=0.5pp, trade_count_sum >=58, affected signals >=4 across >=2 windows, "
            "and survival >=5%."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260522_023_breakout_comms_dual_haircut_risk.py"
        ),
    }
    payload["gate1"]["baseline_artifact"] = BASELINE_ARTIFACT
    payload["gate1"]["baseline_note"] = (
        "Current accepted codebase measured in this run before applying the "
        "dual Communication Services breakout replay scalar."
    )
    payload["llm_metrics"] = {
        "used_llm": False,
        "blocker_relation": (
            "LLM soft-ranking remains attribution-limited; this deterministic "
            "risk scout uses existing production-visible sizing tags."
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "promotion_requirement": (
            "If accepted, implement the dual-haircut scalar in shared "
            "portfolio_engine.py/backtester attribution and run.py output, add "
            "parity tests, then rerun the canonical three windows."
        ),
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM, Form4/options, state-surface, broad-market, ETF, and SEC "
        "nearby retunes because recent logs show data limits or high same-family "
        "multiple-testing risk. This changes one deterministic current-stack "
        "risk-allocation variable."
    )
    payload["known_risks"] = [
        "High multiple-testing risk: this is an existing-haircut residual family.",
        "The affected Communication Services breakout cohort may be sample-thin.",
        "Replay-only positive evidence would still require shared production/backtest implementation before orders change.",
    ]
    payload["interpretation"] = (
        "Dual Communication Services breakout risk cleared Gate 4 and should be "
        "implemented only through shared production/backtest policy."
        if payload["gate4"]["passed"]
        else (
            "Do not promote a dual Communication Services breakout scalar now; "
            "the current-stack clue is too small or unstable after the canonical gate."
        )
    )
    payload["rejection_reason"] = None if payload["gate4"]["passed"] else payload["interpretation"]
    payload["next_evidence_needed"] = (
        None
        if payload["gate4"]["passed"]
        else (
            "Reopen only with new forward closed Communication Services breakout "
            "rows or a distinct production-visible event-quality discriminator."
        )
    )
    payload["related_files"] = [
        "quant/experiments/exp_20260522_023_breakout_comms_dual_haircut_risk.py",
        f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
        f"experiments/logs/{EXPERIMENT_ID}.json",
        f"experiments/tickets/{EXPERIMENT_ID}.json",
        f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
        "docs/experiment_log.jsonl",
    ]
    payload["anti_js"] = "No JavaScript was used."
    return payload


def main() -> None:
    payload = build_payload()
    prior.base.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "selected_risk_multiplier": payload["parameters"]["selected_risk_multiplier"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "improved_windows": payload["gate4"]["improved_windows"],
                "regressed_windows": payload["gate4"]["regressed_windows"],
                "adjusted_signal_count": payload["gate4"]["adjusted_signal_count"],
                "affected_window_count": payload["gate4"]["affected_window_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
