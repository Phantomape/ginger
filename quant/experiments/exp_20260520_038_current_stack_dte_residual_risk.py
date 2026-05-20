"""exp-20260520-038: current-stack DTE residual risk scout.

Alpha search. Tests one current-stack risk-allocation variable: whether signals
already tagged by existing DTE risk multipliers still deserve residual risk.

Entries, exits, ranking, universe, slots, heat, LLM/news, and the existing DTE
field definitions stay fixed. This is replay-only unless a future promotion
adds a shared production/backtest policy and reruns the canonical windows.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from typing import Any

import exp_20260516_039_tsm_core_adaptation as prior


EXPERIMENT_ID = "exp-20260520-038"
EXPERIMENT_SLUG = "current_stack_dte_residual_risk"
MULTIPLIER_KEY = "current_stack_dte_residual_risk_multiplier_applied"
DTE_KEYS = {
    "trend_tech_dte_risk_multiplier_applied",
    "breakout_financials_dte_risk_multiplier_applied",
    "breakout_tech_dte_risk_multiplier_applied",
    "breakout_healthcare_dte_risk_multiplier_applied",
    "trend_healthcare_dte_risk_multiplier_applied",
    "trend_consumer_near_high_dte_risk_multiplier_applied",
}
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 3
BASELINE_ARTIFACT = (
    f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json#before_metrics"
)
TRIAL_ACCOUNTING = {
    "trial_family": "current_stack_dte_residual_risk",
    "changed_variable": "current_stack_dte_residual_risk_multiplier",
    "prior_trial_count": 4,
    "nearby_prior_experiments": [
        "exp-20260505-016",
        "exp-20260516-020",
        "exp-20260517-007",
        "exp-20260520-018",
    ],
    "multiple_testing_risk_bucket": "high",
    "new_evidence_type": "canonical_current_stack_cross_dte_cohort",
}


def _active_dte_keys(sig: dict[str, Any]) -> list[str]:
    sizing = sig.get("sizing") or {}
    active: list[str] = []
    for key in DTE_KEYS:
        value = sizing.get(key)
        if value not in (None, 1, 1.0, False):
            active.append(key)
    return sorted(active)


def _target_signal(sig: dict[str, Any]) -> bool:
    return bool(_active_dte_keys(sig))


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
    out["current_stack_dte_residual_active_keys"] = [
        key for key in sorted(DTE_KEYS) if sizing.get(key) not in (None, 1, 1.0, False)
    ]
    out["current_stack_dte_residual_baseline_shares"] = shares
    out["current_stack_dte_residual_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _target_trade(trade: dict[str, Any]) -> bool:
    multipliers = trade.get("sizing_multipliers") or {}
    return any(multipliers.get(key) not in (None, 1, 1.0, False) for key in DTE_KEYS)


def _build_lifecycle_diagnostic(
    before_runs: dict[str, dict[str, Any]],
    identity_candidates: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    trades: list[dict[str, Any]] = []
    for label, run in before_runs.items():
        tickers = {
            str(trade.get("ticker") or "").upper()
            for trade in run["trades"]
            if _target_trade(trade)
        }
        rows_by_ticker = {
            ticker: prior._load_ohlcv_rows(prior.WINDOWS[label]["snapshot"], ticker)
            for ticker in tickers
        }
        for trade in run["trades"]:
            ticker = str(trade.get("ticker") or "").upper()
            if _target_trade(trade):
                diag = prior._diagnose_trade(label, trade, rows_by_ticker[ticker])
                diag["active_dte_keys"] = [
                    key
                    for key in sorted(DTE_KEYS)
                    if (trade.get("sizing_multipliers") or {}).get(key)
                    not in (None, 1, 1.0, False)
                ]
                trades.append(diag)

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

    by_key: dict[str, dict[str, Any]] = {}
    for trade in trades:
        for key in trade.get("active_dte_keys") or []:
            row = by_key.setdefault(
                key,
                {"trade_count": 0, "win_count": 0, "total_pnl": 0.0, "tickers": set()},
            )
            row["trade_count"] += 1
            pnl = float(trade.get("pnl") or 0.0)
            row["win_count"] += 1 if pnl > 0 else 0
            row["total_pnl"] += pnl
            row["tickers"].add(trade.get("ticker"))

    return {
        "status": "observed_only",
        "target": "signals with existing non-neutral DTE sizing tags",
        "trade_count": len(trades),
        "win_count": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0),
        "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "horizon_summary": horizon_summary,
        "by_dte_key": {
            key: {
                "trade_count": row["trade_count"],
                "win_count": row["win_count"],
                "total_pnl": round(row["total_pnl"], 2),
                "tickers": sorted(ticker for ticker in row["tickers"] if ticker),
            }
            for key, row in sorted(by_key.items())
        },
        "candidate_signals_by_window": identity_candidates,
        "trades": trades,
    }


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Residual scalar | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
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
            f"# {EXPERIMENT_ID} Current-Stack DTE Residual Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing residual risk scalar for already-qualified signals with an existing non-neutral DTE risk tag.",
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
            f"Selected non-control residual scalar: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only. Any positive promotion would need shared portfolio-engine policy, parity tests, and another canonical three-window run.",
            "",
            "No JavaScript was used.",
        ]
    )


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.TARGET_TICKER = "CURRENT_STACK_DTE_RESIDUAL"
    prior.TARGET_STRATEGIES = {"trend_long", "breakout_long"}
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
        "Current accepted codebase measured before applying a residual scalar to "
        "signals already tagged by existing DTE risk multipliers."
    )
    payload.update(TRIAL_ACCOUNTING)
    payload["status"] = (
        "accepted_for_shared_policy_implementation"
        if payload["gate4"]["passed"]
        else "rejected_current_stack_dte_residual_risk"
    )
    payload["decision"] = payload["status"]
    payload["hypothesis"] = (
        "Existing DTE proximity haircuts identify a residual weak pocket in the "
        "current core stack. Applying one additional post-sizing residual scalar "
        "only when a signal already carries a non-neutral DTE risk tag may improve "
        "EV without changing entry, ranking, exits, slots, or LLM/news behavior."
    )
    payload["change_type"] = "risk_allocation_shadow"
    payload["changed_variable"] = "current_stack_dte_residual_risk_multiplier"
    payload["single_causal_variable"] = (
        "post-sizing residual risk scalar for existing core signals with active DTE risk tags"
    )
    payload["parameters"].update(
        {
            "active_dte_keys": sorted(DTE_KEYS),
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "risk allocation: current-stack signals already tagged by DTE risk "
            "multipliers may still consume too much residual capital."
        ),
        "2_history_check": {
            "nearby_rejections": (
                "exp-20260505-016 and exp-20260517-007 tested narrower breakout "
                "DTE zero/haircut variants; exp-20260516-020 accepted a 0.125x "
                "Technology trend DTE scalar after 0.0x failed under the older stack."
            ),
            "new_evidence": (
                "The current accepted stack now shows the cross-DTE residual "
                "executed cohort at 7 trades, 0 winners, across all three windows."
            ),
            "anti_repeat": (
                "High multiple-testing risk; the run is not retainable unless "
                "it clears strict sample, no-regression, and cross-window gates."
            ),
        },
        "3_single_causal_variable": "current_stack_dte_residual_risk_multiplier",
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three fixed windows; aggregate EV/PnL "
            "positive, >=2 improved windows, no EV-regressed windows, survival "
            ">=5%, affected signals >=6 across all 3 windows, and drawdown drift <=0.5pp."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260520_038_current_stack_dte_residual_risk.py"
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "promotion_requirement": (
            "If accepted, add a shared residual DTE risk policy used by both "
            "backtester.py and run.py through portfolio_engine.py, add attribution "
            "and parity tests, then rerun all canonical windows."
        ),
    }
    payload["llm_metrics"] = {
        "used_llm": False,
        "blocker_relation": (
            "No LLM behavior changed; this is a deterministic current-stack "
            "DTE residual risk-budget scout."
        ),
    }
    payload["why_not_other_changes"] = (
        "LLM soft-ranking remains replay-attribution limited; state-surface and "
        "broad-market local scalar retunes are under anti-repeat; SEC fact/tone "
        "work lacks phrase provenance. This deterministic current-stack DTE "
        "cohort has enough cross-window sample to test as alpha_search."
    )
    payload["known_risks"] = [
        "This is high multiple-testing risk because nearby DTE scalar experiments exist.",
        "Zeroing residual risk can free slots and alter replacement trades.",
        "A passing replay would still require shared production/backtest policy before promotion.",
    ]
    if payload["gate4"]["passed"]:
        payload["interpretation"] = (
            "The current-stack DTE residual scalar cleared the replay gate, but "
            "promotion still needs shared policy/parity implementation."
        )
        payload["rejection_reason"] = None
    else:
        payload["interpretation"] = (
            "The current-stack DTE residual scalar did not clear Gate 4; keep "
            "existing DTE policies unchanged."
        )
        payload["rejection_reason"] = payload["interpretation"]
    payload["next_evidence_needed"] = (
        "Do not retry nearby DTE residual scalars without new forward DTE-tagged "
        "outcomes or a distinct event-quality field."
    )
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        "quant/experiments/exp_20260520_038_current_stack_dte_residual_risk.py",
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
                "selected_residual_scalar": payload["parameters"][
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
