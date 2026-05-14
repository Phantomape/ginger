"""exp-20260514-001: core actual-risk ceiling allocation scout.

Alpha search. Tests one production-visible allocation variable: after all
existing shared sizing helpers have run, cap core trend/breakout actual risk
per entry by shrinking shares. The scout does not change entries, ranking,
exits, targets, the universe, LLM/news behavior, or any existing multiplier.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-001"
EXPERIMENT_SLUG = "core_actual_risk_ceiling"
MULTIPLIER_KEY = "core_actual_risk_ceiling_applied"
RISK_CEILINGS = [0.018, 0.020, 0.0225, 0.025]

CURRENT_RISK_CEILING = 0.020


def _rescale_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    risk_ceiling: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    risk_pct = sizing.get("risk_pct")
    if shares <= 0 or not isinstance(risk_pct, (int, float)):
        return sizing
    if float(risk_pct) <= risk_ceiling:
        return sizing

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or net_risk_per_share <= 0 or portfolio_value <= 0:
        return sizing

    cap_shares = int(math.floor((portfolio_value * risk_ceiling) / net_risk_per_share))
    new_shares = max(1, min(shares, cap_shares))
    if new_shares >= shares:
        return sizing

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    out = dict(sizing)
    out["core_actual_risk_ceiling_before_risk_pct"] = float(risk_pct)
    out["core_actual_risk_ceiling_before_shares"] = shares
    out["core_actual_risk_ceiling_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value
    out[MULTIPLIER_KEY] = risk_ceiling
    return out


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get("strategy") in {"trend_long", "breakout_long"}:
                adjusted = _rescale_sizing(
                    sig,
                    sizing,
                    CURRENT_RISK_CEILING,
                    portfolio_value,
                )
                if adjusted is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "risk_ceiling": CURRENT_RISK_CEILING,
                            "before_risk_pct": sizing.get("risk_pct"),
                            "after_risk_pct": adjusted.get("risk_pct"),
                            "before_shares": sizing.get("shares_to_buy"),
                            "after_shares": adjusted.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "sizing_multipliers_before": {
                                key: value
                                for key, value in sizing.items()
                                if key.endswith("_multiplier_applied")
                            },
                        }
                    )
                    sig = {**sig, "sizing": adjusted}
            out.append(sig)
        return out

    return wrapped


def _run_variant_window(label: str, risk_ceiling: float) -> dict[str, Any]:
    global CURRENT_RISK_CEILING
    CURRENT_RISK_CEILING = risk_ceiling

    original_size = base.portfolio_engine.size_signals
    original_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS
    base.ADJUSTMENTS = []
    try:
        base.portfolio_engine.size_signals = _make_size_wrapper(original_size)
        if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )
        return base._run_window(label, variant=False)
    finally:
        base.portfolio_engine.size_signals = original_size
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_keys


def _candidate_payload(
    risk_ceiling: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        variant = _run_variant_window(label, risk_ceiling)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and max_drawdown_worse <= 0.0
        and adjusted_count > 0
    )
    return {
        "risk_ceiling": risk_ceiling,
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "adjusted_signal_count": adjusted_count,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    pool = passed if passed else candidates
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "risk_ceiling": row["risk_ceiling"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Risk ceiling | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {cap:.4f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                cap=row["risk_ceiling"],
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Core Actual-Risk Ceiling",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing actual `risk_pct` ceiling for core `trend_long`/`breakout_long` signals. The ceiling shrinks shares after existing shared sizing helpers run; it does not change entries, ranking, exits, targets, universe, LLM, or news behavior.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected risk ceiling: `{payload['parameters']['selected_risk_ceiling']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout unless Gate 4 passes and the same cap is promoted into shared `portfolio_engine` sizing with attribution parity.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False)
        for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(risk_ceiling, before_runs)
        for risk_ceiling in RISK_CEILINGS
    ]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_core_actual_risk_ceiling"
    )
    interpretation = (
        "The post-sizing actual-risk ceiling cleared the canonical three-window gate and should be promoted through shared portfolio sizing before production use."
        if passed
        else "The post-sizing actual-risk ceiling did not clear the canonical three-window gate; leave the accepted sizing stack unchanged and avoid broad actual-risk cap retunes without a narrower discriminator."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Residual tail losses in the accepted stack cluster in positions whose post-sizing actual risk is high after multiple positive helpers stack. A production-visible actual-risk ceiling might preserve the accepted entries while improving EV and drawdown by shrinking only oversized risk units."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "core_post_sizing_actual_risk_ceiling",
        "single_causal_variable": (
            "post-sizing risk_pct ceiling for core trend_long/breakout_long signals"
        ),
        "parameters": {
            "risk_ceiling_sweep": RISK_CEILINGS,
            "selected_risk_ceiling": selected["risk_ceiling"],
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "add-ons",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core risk allocation using post-sizing deployment context / actual risk pressure",
            "2_history_check": {
                "high_exec_rr_core": "Rejected last run; this does not use R:R quality and instead tests downside concentration in post-sizing risk units.",
                "green_and_clean_leader_overlays": "Recent nearby green/clean-leader refinements were rejected; this does not add another positive confirmation overlay.",
                "global_cap_and_heat_sweeps": "Older broad capacity changes failed; this keeps slots, heat, and position caps unchanged and shrinks only realized risk after existing helpers stack.",
                "llm_soft_ranking": "Still data-limited, so no LLM scoring is changed.",
                "SEC/Space": "SEC semantic fields and Space forward replacement evidence are not sufficient for another same-sample retune.",
            },
            "3_single_causal_variable": "core_post_sizing_actual_risk_ceiling",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, no drawdown worsening.",
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_001_core_actual_risk_ceiling.py"
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
                "portfolio_engine sizing risk_pct",
                "portfolio_engine sizing net_risk_per_share",
                "portfolio_engine sizing shares_to_buy",
                "portfolio_value",
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
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": "LLM soft-ranking remains too thin for attributable replay, so this run uses deterministic production-visible sizing state.",
        },
        "production_impact": {
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
        else "Use a narrower production-visible discriminator for oversized post-sizing risk before retrying actual-risk caps.",
        "related_files": [
            "quant/experiments/exp_20260514_001_core_actual_risk_ceiling.py",
            "data/experiments/exp-20260514-001/core_actual_risk_ceiling.json",
            "docs/experiments/logs/exp-20260514-001.json",
            "docs/experiments/tickets/exp-20260514-001.json",
            "docs/experiments/artifacts/exp-20260514-001_core_actual_risk_ceiling.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "High exec-RR was already rejected; LLM/SEC/Space are data-limited or frozen-sample exhausted; green/clean-leader overlays were recently rejected. This tests a different core deployment-context risk variable without adding ticker noise."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "logs"
        / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
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
        "selected_risk_ceiling": payload["parameters"]["selected_risk_ceiling"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    base._upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_risk_ceiling": result["parameters"][
                    "selected_risk_ceiling"
                ],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
