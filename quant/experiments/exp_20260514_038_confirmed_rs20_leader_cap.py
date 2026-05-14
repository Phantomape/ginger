"""exp-20260514-038: confirmed RS20 leader cap scout.

Tests one allocation-only causal variable on the accepted core stack: whether
RS20 entry-state leaders deserve extra cap room only when the signal-day ticker
also outperformed SPY. Entries, exits, ranking, raw multipliers, universe,
LLM/news behavior, portfolio heat, and slot limits stay fixed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260514_037_rs20_entry_state_leader_cap as scout


EXPERIMENT_ID = "exp-20260514-038"
EXPERIMENT_SLUG = "confirmed_rs20_leader_cap"
CAP_KEY = "confirmed_rs20_entry_state_max_position_pct_applied"
CAP_SWEEP = [0.55, 0.60]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _configure_scout() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scout.CAP_KEY = CAP_KEY
    scout.CAP_SWEEP = CAP_SWEEP
    scout.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    scout.CURRENT_RS20_MAX_POSITION_PCT = base.portfolio_engine.MAX_POSITION_PCT
    scout._is_target_sleeve = _is_target_sleeve


def _is_target_sleeve(sig: dict[str, Any], sizing: dict[str, Any]) -> bool:
    return bool(
        sig.get("rs20_entry_state_leader") is True
        and sig.get("signal_day_ticker_outperformed_spy") is True
        and sig.get("strategy") in {"trend_long", "breakout_long"}
        and sizing.get("shares_to_buy")
        and sizing.get("entry_price")
        and sizing.get("net_risk_per_share")
        and sizing.get("base_risk_pct") is not None
    )


def _artifact_paths() -> dict[str, Path]:
    return {
        "artifact": (
            base.REPO_ROOT
            / "data"
            / "experiments"
            / EXPERIMENT_ID
            / f"{EXPERIMENT_SLUG}.json"
        ),
        "log": (
            base.REPO_ROOT
            / "docs"
            / "experiments"
            / "logs"
            / f"{EXPERIMENT_ID}.json"
        ),
        "ticket": (
            base.REPO_ROOT
            / "docs"
            / "experiments"
            / "tickets"
            / f"{EXPERIMENT_ID}.json"
        ),
        "markdown": (
            base.REPO_ROOT
            / "docs"
            / "experiments"
            / "artifacts"
            / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {cap:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                cap=row["max_position_pct"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
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

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Confirmed RS20 Leader Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max-position cap available only to `rs20_entry_state_leader=true` trend/breakout signals where `signal_day_ticker_outperformed_spy=true`. RS20 scalar, entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected cap: `{payload['parameters']['selected_max_position_pct']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.",
        ]
    )


def _write_outputs(payload: dict[str, Any]) -> None:
    paths = _artifact_paths()
    base._write_json(paths["artifact"], payload)
    base._write_json(paths["log"], payload)
    base._write_json(
        paths["ticket"],
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Confirmed RS20 leader cap scout",
            "status": payload["decision"],
            "artifact": str(paths["artifact"].relative_to(base.REPO_ROOT)),
            "log": str(paths["log"].relative_to(base.REPO_ROOT)),
            "markdown": str(paths["markdown"].relative_to(base.REPO_ROOT)),
            "summary": payload["interpretation"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "gate4": payload["gate4"],
        },
    )
    paths["markdown"].parent.mkdir(parents=True, exist_ok=True)
    paths["markdown"].write_text(_markdown(payload) + "\n", encoding="utf-8")
    scout._upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


def _build_payload(
    gate2: dict[str, Any],
    selected: dict[str, Any],
    sweep_results: list[dict[str, Any]],
) -> dict[str, Any]:
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_confirmed_rs20_leader_cap"
    )
    interpretation = (
        "Confirmed RS20 leaders remained cap-bound and the selected cap improved the canonical three-window stack without EV regression or unacceptable drawdown drift."
        if selected["passed"]
        else "The confirmed RS20 leader cap did not beat the accepted core stack across the canonical three-window gate."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Broad RS20 cap expansion was too blunt. The RS20 entry-state leader "
            "sleeve may deserve extra max-position room only when the signal-day "
            "ticker also outperformed SPY, preserving continuation convexity while "
            "avoiding weaker RS20 leaders."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "max_position_pct_for_confirmed_rs20_entry_state_leaders",
        "single_causal_variable": (
            "max_position_pct for rs20_entry_state_leader=true and "
            "signal_day_ticker_outperformed_spy=true"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "baseline_default_max_position_pct": base.portfolio_engine.MAX_POSITION_PCT,
            "selected_max_position_pct": selected["max_position_pct"],
            "target_sleeve": {
                "rs20_entry_state_leader": True,
                "signal_day_ticker_outperformed_spy": True,
                "strategy": ["trend_long", "breakout_long"],
            },
            "rs20_entry_state_risk_multiplier_unchanged": (
                base.portfolio_engine.RS20_ENTRY_STATE_RISK_MULTIPLIER
            ),
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "RS20 risk multiplier",
                "clean-SPY scalar and cap",
                "all other sizing multipliers",
                "all existing cap rules",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260514-037": (
                    "Broad RS20 entry-state leader cap improved EV/PnL but failed "
                    "the drawdown guardrail; this run adds signal-day SPY "
                    "outperformance as the new segmentation variable requested by "
                    "that rejection."
                ),
                "exp-20260514-034/035": (
                    "Clean-SPY qualifier and breakout-only scope tests were no-op "
                    "or regressive; this run does not alter clean-SPY logic."
                ),
                "exp-20260514-030": (
                    "Accepted Financials mid-dispersion leader cap remains part of "
                    "the baseline; this run only adds room for a separate confirmed "
                    "RS20 intersection if it is already cap-bound."
                ),
            },
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains production-sample limited, so this run "
                "uses existing deterministic fields rather than forcing an "
                "unreliable LLM alpha."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: RS20 leaders with signal-day SPY "
                "outperformance may be the subset worth extra capacity"
            ),
            "2_history_check": (
                "Broad RS20 cap expansion failed drawdown in exp-20260514-037; "
                "this is not a nearby scalar retry because it requires a new "
                "production-visible confirmation field."
            ),
            "3_single_causal_variable": (
                "confirmed RS20 leader max_position_pct; all multipliers and "
                "filters remain fixed"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, max DD worse <= 0.5pp, nonzero "
                "adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_038_confirmed_rs20_leader_cap.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
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
                "portfolio_engine rs20_entry_state_leader",
                "portfolio_engine signal_day_ticker_outperformed_spy",
                "portfolio_engine strategy",
                "portfolio_engine sizing base_risk_pct",
                "portfolio_engine sizing max_position_pct_applied",
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
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "sweep_summary": scout._sweep_summary(sweep_results),
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains production-aligned sample limited; "
                "this deterministic allocation test is replayable on fixed "
                "OHLCV snapshots."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_accepted": (
                "Move the cap into shared constants/portfolio_engine and add "
                "attribution plus parity tests before any live/default impact."
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
        "rejection_reason": None
        if selected["passed"]
        else "Gate 4 failed for confirmed RS20 cap expansion under the canonical three-window protocol.",
        "next_evidence_needed": (
            "If rejected, stop retrying RS20 cap room and pivot to a different "
            "allocation/ranking state variable or a high-quality candidate-pool "
            "expansion with non-noisy inclusion criteria."
        ),
    }


def run() -> dict[str, Any]:
    _configure_scout()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: scout._run_window(label, None) for label in base.WINDOWS}
    sweep_results = [
        scout._candidate_payload(cap, before_runs) for cap in CAP_SWEEP
    ]
    selected_summary = scout._select_candidate(sweep_results)
    selected = scout._candidate_payload(
        selected_summary["max_position_pct"],
        before_runs,
        include_details=True,
    )
    payload = _build_payload(gate2, selected, sweep_results)
    _write_outputs(payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4": result["gate4"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
