"""exp-20260514-045: triple momentum leader cap scout.

Tests one allocation-only causal variable on the accepted core stack: whether
RS20 entry-state leaders deserve extra max-position room only when confirmed by
both RS60 top-quintile state and a signal-day green candle. Entries, exits,
ranking, raw multipliers, universe, LLM/news behavior, portfolio heat, and slot
limits stay fixed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260514_037_rs20_entry_state_leader_cap as scout


EXPERIMENT_ID = "exp-20260514-045"
EXPERIMENT_SLUG = "triple_momentum_leader_cap"
CAP_KEY = "triple_momentum_leader_max_position_pct_applied"
CAP_SWEEP = [0.50, 0.525, 0.55]
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
        and sig.get("rs60_top_quintile_state") is True
        and sig.get("signal_day_ticker_green_candle") is True
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
            f"# {EXPERIMENT_ID} Triple Momentum Leader Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max-position cap available only to `rs20_entry_state_leader=true`, `rs60_top_quintile_state=true`, and `signal_day_ticker_green_candle=true` trend/breakout signals. Entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.",
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
            "title": "Triple momentum leader cap scout",
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
        else "rejected_triple_momentum_leader_cap"
    )
    interpretation = (
        "Triple-confirmed momentum leaders remained cap-bound and the selected cap improved the canonical three-window stack without EV regression or unacceptable drawdown drift."
        if selected["passed"]
        else "The triple-confirmed momentum leader cap did not beat the accepted core stack across the canonical three-window gate."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Broad RS20 cap expansion and SPY-confirmed RS20 cap expansion were too blunt. "
            "A narrower intersection of RS20 entry leadership, RS60 top-quintile persistence, "
            "and a green signal-day candle may identify cap-bound continuation winners worth "
            "extra position room without adding a filter or changing ranking."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "max_position_pct_for_triple_confirmed_momentum_leaders",
        "single_causal_variable": (
            "max_position_pct for rs20_entry_state_leader=true, "
            "rs60_top_quintile_state=true, and signal_day_ticker_green_candle=true"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "baseline_default_max_position_pct": base.portfolio_engine.MAX_POSITION_PCT,
            "selected_max_position_pct": selected["max_position_pct"],
            "target_sleeve": {
                "rs20_entry_state_leader": True,
                "rs60_top_quintile_state": True,
                "signal_day_ticker_green_candle": True,
                "strategy": ["trend_long", "breakout_long"],
            },
            "existing_multipliers_unchanged": {
                "rs20_entry_state": base.portfolio_engine.RS20_ENTRY_STATE_RISK_MULTIPLIER,
                "rs60_top_quintile": base.portfolio_engine.RS60_TOP_QUINTILE_RISK_MULTIPLIER,
                "signal_day_green": base.portfolio_engine.SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER,
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all risk multipliers",
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
                    "Broad RS20 entry-state leader cap produced PnL but failed the drawdown "
                    "guardrail; this run adds RS60 persistence and same-day green confirmation."
                ),
                "exp-20260514-038": (
                    "SPY-confirmed RS20 cap still failed Gate 4; this run uses internal "
                    "ticker momentum confirmation instead of SPY-relative confirmation."
                ),
                "exp-20260514-019": (
                    "RS60 top-quintile cap was rejected as a broad sleeve; this run requires "
                    "RS60 only as one leg of a tighter triple-confirmed state."
                ),
                "exp-20260514-032": (
                    "Green-candle SPY confirmation was rejected; this run does not alter green "
                    "eligibility or require SPY outperformance."
                ),
            },
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains production-sample limited, so this run uses existing "
                "deterministic, replayable fields instead of forcing an unreliable LLM alpha."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: triple-confirmed momentum leaders may be under-allocated "
                "because accepted momentum scalars can run into the default cap"
            ),
            "2_history_check": (
                "Broad RS20 and SPY-confirmed RS20 cap tests failed; this run changes the "
                "segmentation state, not the scalar or the broad RS20 cap."
            ),
            "3_single_causal_variable": (
                "triple-confirmed momentum leader max_position_pct; all multipliers and filters remain fixed"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two "
                "EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, "
                "nonzero adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_045_triple_momentum_leader_cap.py"
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
                "portfolio_engine rs60_top_quintile_state",
                "portfolio_engine signal_day_ticker_green_candle",
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
            "minimum_after_survival_rate": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ],
            "passed": selected["delta_metrics"]["aggregate_after"]["survival_rate_min"]
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
                "LLM soft-ranking remains production-aligned sample limited; this "
                "deterministic allocation test is replayable on fixed OHLCV snapshots."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_accepted": (
                "Move the cap into shared constants/portfolio_engine and add attribution "
                "plus parity tests before any live/default impact."
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
        else "Gate 4 failed for triple-confirmed momentum leader cap expansion under the canonical three-window protocol.",
        "next_evidence_needed": (
            "If rejected, stop retrying RS20/RS60/green cap-room combinations unless new "
            "forward attribution identifies a different cap-bound winner cluster."
        ),
        "related_files": [
            "quant/experiments/exp_20260514_045_triple_momentum_leader_cap.py",
            "data/experiments/exp-20260514-045/triple_momentum_leader_cap.json",
            "docs/experiments/logs/exp-20260514-045.json",
            "docs/experiments/tickets/exp-20260514-045.json",
            "docs/experiments/artifacts/exp-20260514-045_triple_momentum_leader_cap.md",
            "docs/experiment_log.jsonl",
        ],
    }


def run() -> dict[str, Any]:
    _configure_scout()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: scout._run_window(label, None) for label in base.WINDOWS}
    sweep_results = [scout._candidate_payload(cap, before_runs) for cap in CAP_SWEEP]
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
