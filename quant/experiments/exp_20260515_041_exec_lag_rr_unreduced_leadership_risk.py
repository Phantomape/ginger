"""exp-20260515-041: unreduced exec-lag R:R leadership risk.

This tests one allocation refinement after exp-20260515-038/039:
same-day top-quartile ``exec_lag_adj_net_rr`` signals get a small cap-aware
top-up only when existing shared sizing policy has not already applied a risk
haircut. The goal is to test a production-visible drawdown discriminator
without changing entries, filters, ranking, exits, targets, universe, slots,
heat, LLM, or news behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260515_038_exec_lag_rr_leadership_risk as prior


EXPERIMENT_ID = "exp-20260515-041"
EXPERIMENT_SLUG = "exec_lag_rr_unreduced_leadership_risk"
MULTIPLIER_KEY = "exec_lag_rr_unreduced_leadership_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _prior_haircut_keys(sizing: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key, value in sizing.items():
        if not key.endswith("_risk_multiplier_applied"):
            continue
        if key == MULTIPLIER_KEY:
            continue
        if isinstance(value, (int, float)) and value < 1.0:
            keys.append(key)
    return sorted(keys)


def _make_size_wrapper(
    original_size_signals: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapper(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        *args: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        sized = original_size_signals(signals, portfolio_value, *args, **kwargs)
        adjusted: list[dict[str, Any]] = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            haircut_keys = _prior_haircut_keys(sizing)
            if not sig.get("exec_lag_rr_leadership_state") or haircut_keys:
                adjusted.append(sig)
                continue

            new_sizing = prior._scale_sizing(
                sizing,
                prior.sweep.CURRENT_RISK_MULTIPLIER,
                portfolio_value,
            )
            if new_sizing is not sizing:
                new_sizing = dict(new_sizing)
                multiplier = new_sizing.pop(prior.MULTIPLIER_KEY, None)
                if multiplier is not None:
                    new_sizing[MULTIPLIER_KEY] = multiplier
                prior.base.ADJUSTMENTS.append(
                    {
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sig.get("sector"),
                        "exec_lag_adj_net_rr": sig.get("exec_lag_adj_net_rr"),
                        "exec_lag_rr_leadership_cutoff": sig.get(
                            "exec_lag_rr_leadership_cutoff"
                        ),
                        "baseline_shares": sizing.get("shares_to_buy"),
                        "new_shares": new_sizing.get("shares_to_buy"),
                        "baseline_position_value": sizing.get("position_value_usd"),
                        "new_position_value": new_sizing.get("position_value_usd"),
                        "cap_shares": new_sizing.get(
                            "exec_lag_rr_leadership_cap_shares"
                        ),
                        "skipped_prior_haircut_keys": haircut_keys,
                        "core_confirmed_quality_state": sig.get(
                            "core_confirmed_quality_state"
                        ),
                        "rs20_entry_state_leader": sig.get(
                            "rs20_entry_state_leader"
                        ),
                        "rs60_top_quintile_state": sig.get(
                            "rs60_top_quintile_state"
                        ),
                        "price_vs_200ma_extension_state": sig.get(
                            "price_vs_200ma_extension_state"
                        ),
                        "signal_day_ticker_green_candle": sig.get(
                            "signal_day_ticker_green_candle"
                        ),
                        "signal_day_ticker_outperformed_spy": sig.get(
                            "signal_day_ticker_outperformed_spy"
                        ),
                        "trade_quality_score": sig.get("trade_quality_score"),
                        "regime_exit_bucket": sig.get("regime_exit_bucket"),
                        "regime_exit_score": sig.get("regime_exit_score"),
                    }
                )
                sig = {**sig, "sizing": new_sizing}
            adjusted.append(sig)
        return adjusted

    return wrapper


def _risk_distribution(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            "worst_trade_pct": row.get("worst_trade_pct"),
            "max_consecutive_losses": row.get("max_consecutive_losses"),
            "tail_loss_share": row.get("tail_loss_share"),
        }
        for label, row in metrics.items()
    }


def _markdown(payload: dict[str, Any]) -> str:
    selected = payload["selected_candidate"]
    lines = [
        f"# {EXPERIMENT_ID} Exec-Lag R:R Unreduced Leadership Risk",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single variable: cap-aware post-sizing top-up for `trend_long` / `breakout_long` non-ETF/non-commodity stock signals whose `exec_lag_adj_net_rr` is in the same-day top quartile and whose existing sizing did not already carry a risk-haircut multiplier below 1.0. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.",
        "",
        "## Sweep",
        "",
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {mult:.4f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )
    lines.extend(
        [
            "",
            f"Selected multiplier: `{selected['risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in prior.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    lines.extend(
        [
            "",
            "Production impact: replay-only scout. A positive promotion must move the state and sizing helper into shared `risk_engine.py` / `portfolio_engine.py`, add attribution keys, update parity docs, and add focused tests before production behavior changes.",
        ]
    )
    return "\n".join(lines)


def _configure_modules() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    prior.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    prior._make_size_wrapper = _make_size_wrapper
    prior._markdown = _markdown

    prior.sweep.EXPERIMENT_ID = EXPERIMENT_ID
    prior.sweep.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.sweep.MULTIPLIER_KEY = MULTIPLIER_KEY
    prior.sweep.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    prior.sweep.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: prior.base._run_window(label, variant=False)
        for label in prior.base.WINDOWS
    }
    candidates = [
        prior.sweep._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = prior.sweep._select_candidate(candidates)
    passed = bool(selected["passed"])
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_exec_lag_rr_unreduced_leadership_risk"
    )
    interpretation = (
        "Unreduced exec-lag R:R leadership cleared the canonical three-window gate; promote only through shared production/backtest policy."
        if passed
        else "Unreduced exec-lag R:R leadership did not clear the canonical three-window gate; do not promote this allocation state on the frozen windows."
    )
    selected_candidate = {
        "risk_multiplier": selected["risk_multiplier"],
        "aggregate_before": selected["delta_metrics"]["aggregate_before"],
        "aggregate_after": selected["delta_metrics"]["aggregate_after"],
        "aggregate_delta": selected["delta_metrics"]["aggregate_delta"],
        "before": selected["before_metrics"],
        "after": selected["after_metrics"],
        "delta": selected["delta_metrics"]["by_window"],
        "passes": selected["passed"],
        "gate4": selected["gate4"],
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "High exec-lag-adjusted R:R was directionally positive but old-window fragile in exp-20260515-038, "
            "and breakout-only narrowing was underpowered in exp-20260515-039. If the fragility comes from "
            "overriding existing shared de-risking states, then applying the same top-quartile R:R top-up only to "
            "signals with no pre-existing risk haircut should preserve the payoff edge while reducing drawdown leakage."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "exec_lag_rr_unreduced_leadership_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for top-quartile exec_lag_adj_net_rr stock signals only when existing sizing has no *_risk_multiplier_applied value below 1.0"
        ),
        "parameters": {
            "rr_top_fraction": prior.RR_TOP_FRACTION,
            "excluded_sectors": sorted(prior.EXCLUDED_SECTORS),
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "requires_no_existing_risk_multiplier_below_1": True,
            "anti_js": "No JavaScript was used.",
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "MAX_POSITIONS",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
        },
        "historical_experiment_check": {
            "exp-20260515-038": (
                "Top-quartile exec_lag_adj_net_rr improved aggregate EV/PnL but failed Gate 4 because old_thin regressed and the largest scalar breached drawdown."
            ),
            "exp-20260515-039": (
                "Breakout-leadership narrowing was positive only in late_strong and failed Gate 4."
            ),
            "exp-20260515-027": (
                "The no-prior-haircut idea failed for trend price-extension eligibility, but this is a different mechanism: R:R geometry should not undo explicit de-risking states."
            ),
            "blocked_branches_avoided": (
                "LLM soft-ranking remains data-limited; Space and raw candidate-pool expansion were recently rejected or sample-limited."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "core risk allocation: high exec-lag-adjusted R:R is useful only when it does not override a prior shared risk haircut."
            ),
            "2_history_check": (
                "exp038 high-R:R was directionally positive but old_thin/drawdown fragile; exp039 breakout-only narrowing was underpowered; no unreduced high-R:R scout was found."
            ),
            "3_single_causal_variable": (
                "exec_lag_rr_unreduced_leadership_risk_multiplier with a fixed top-quartile R:R state and fixed no-prior-haircut gate"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, min survival >= 5%, trade_count >= 50, max DD worse <= 0.5pp, adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_041_exec_lag_rr_unreduced_leadership_risk.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": prior.base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine exec_lag_adj_net_rr",
                "portfolio_engine existing *_risk_multiplier_applied fields",
                "portfolio_engine max_position_pct_applied",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_survived_sum"
            ],
            "minimum_after_survival_rate": selected["delta_metrics"][
                "aggregate_after"
            ]["survival_rate_min"],
            "passed": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ]
            >= 0.05,
        },
        "gate4": selected["gate4"],
        "selected_candidate": selected_candidate,
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": prior.sweep._sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "risk_distribution": {
            "before": _risk_distribution(selected["before_metrics"]),
            "after": _risk_distribution(selected["after_metrics"]),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Recent records show LLM soft-ranking is attribution/data-limited, so this run used deterministic shared fields."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_accepted": (
                "Move the top-quartile R:R state and no-prior-haircut sizing top-up into shared risk/portfolio modules, add backtester attribution keys, update production_backtest_parity.md, and add focused parity tests before live behavior changes."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "Do not retry simple exec_lag_adj_net_rr or no-prior-haircut R:R scalars on these frozen windows without a new production-visible drawdown/catalyst discriminator."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_041_exec_lag_rr_unreduced_leadership_risk.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "This avoids LLM soft-ranking, Space mature-cohort expansion, and raw candidate-pool growth because recent logs mark those paths data-limited or rejected. "
            "It keeps the fixed core candidate set and tests one production-visible allocation discriminator."
        ),
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(prior.base._safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        prior.base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        prior.base.REPO_ROOT
        / "docs"
        / "experiments"
        / "logs"
        / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        prior.base.REPO_ROOT
        / "docs"
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        prior.base.REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(prior.base.REPO_ROOT)),
    }
    prior.base._write_json(artifact_path, payload)
    prior.base._write_json(log_path, payload)
    prior.base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(payload["artifact_markdown"] + "\n", encoding="utf-8")
    _upsert_jsonl(prior.base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_risk_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "sweep_summary": result["sweep_summary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
