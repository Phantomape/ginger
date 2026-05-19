"""exp-20260515-006: low-score plain risk-on cap scout.

Tests one production-visible allocation variable on the accepted core stack:
otherwise-unmodified risk-on signals already using the accepted low-score
1.5x risk budget may still be clipped by the default 40% single-position cap.

This is a shadow scout. It reuses the deterministic cap replay harness from
exp-20260515-007, but points the target sleeve at the separate 1.5x low-score
risk-on path.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260515_007_mid_score_plain_risk_on_cap as scout


EXPERIMENT_ID = "exp-20260515-006"
EXPERIMENT_SLUG = "low_score_plain_risk_on_cap"
CAP_KEY = "low_score_plain_risk_on_max_position_pct_applied"
CAP_AUX_PREFIX = "low_score_plain_risk_on_cap"
CAP_SWEEP = [0.425, 0.45, 0.475, 0.50]
TARGET_MULTIPLIER = 1.5


def _configure_scout() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    scout.CAP_KEY = CAP_KEY
    scout.CAP_AUX_PREFIX = CAP_AUX_PREFIX
    scout.CAP_SWEEP = CAP_SWEEP
    scout.MID_SCORE_MULTIPLIER = TARGET_MULTIPLIER
    scout.CURRENT_MAX_POSITION_PCT = CAP_SWEEP[0]


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
    for label in scout.base.WINDOWS:
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
                adj=len(payload["adjustments"].get(label, [])),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Low-Score Plain Risk-On Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max-position cap for otherwise-unmodified risk-on signals that already use the accepted low-score 1.5x sizing path. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "## Selected Candidate",
            "",
            *window_rows,
            "",
            "Production impact: shadow scout only. Positive promotion requires a shared `portfolio_engine` policy plus attribution/parity tests before live/default behavior changes.",
        ]
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(scout.base._safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(scout.base._safe(payload), ensure_ascii=True, sort_keys=True)
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
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    _configure_scout()
    gate2 = scout.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: scout._run_window(label, None) for label in scout.base.WINDOWS
    }
    sweep_results = [scout._candidate_payload(cap, before_runs) for cap in CAP_SWEEP]
    selected_summary = scout._select_candidate(sweep_results)
    selected = scout._candidate_payload(
        selected_summary["max_position_pct"],
        before_runs,
        include_details=True,
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_low_score_plain_risk_on_cap"
    )
    interpretation = (
        "Low-score plain risk-on signals were cap-bound and the selected cap improved the canonical three-window stack without EV regression."
        if selected["passed"]
        else "Low-score plain risk-on cap expansion did not clear the canonical three-window gate."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted low-score plain risk-on 1.5x sleeve may still be clipped by the generic 40% cap. A sleeve-only cap lift could improve allocation without changing entries, exits, ranking, or raw risk multipliers."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "max_position_pct_for_low_score_plain_risk_on",
        "single_causal_variable": (
            "max_position_pct for otherwise-unmodified risk-on signals with risk_on_unmodified_risk_multiplier_applied == 1.5"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "baseline_default_max_position_pct": scout.BASELINE_MAX_POSITION_PCT,
            "selected_max_position_pct": selected["max_position_pct"],
            "target_sleeve": {
                "strategy": ["trend_long", "breakout_long"],
                "regime_exit_bucket": "risk_on",
                "risk_on_unmodified_risk_multiplier_applied": TARGET_MULTIPLIER,
                "spy_relative_leader_risk_on_multiplier_applied": 1.0,
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "raw risk_on_unmodified multipliers",
                "all other sizing multipliers",
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
                "exp-20260430-031": (
                    "Low-score plain risk-on multiplier tuning established this sleeve; this run does not retune the multiplier."
                ),
                "exp-20260430-013": (
                    "Rejected residual high-score plain risk-on multiplier retune; this run targets low-score cap room instead."
                ),
                "exp-20260501-024": (
                    "Accepted SPY-relative leader risk allocation inside plain risk-on; this run excludes that leader branch."
                ),
                "exp-20260502-021": (
                    "Accepted SPY-relative leader cap expansion; this run tests the separate non-leader low-score sleeve."
                ),
                "exp-20260515-007": (
                    "Rejected the adjacent mid-score cap scout as strict null with zero adjusted signals; this run tests a different accepted score bucket."
                ),
            },
            "why_not_llm_or_space": (
                "LLM soft-ranking remains attribution-limited, and the latest Space benchmark-breadth refinements were adjacent scalar retries. This run uses deterministic fields already emitted by shared production sizing."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: accepted low-score plain risk-on signals may deserve cap room above the generic 40% position cap."
            ),
            "2_history_check": (
                "Prior plain risk-on work tuned risk multipliers and SPY-leader caps. The immediately prior mid-score cap was a strict null; no low-score non-leader position-cap scout was found."
            ),
            "3_single_causal_variable": "low-score plain risk-on max_position_pct only.",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, nonzero adjustments."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_006_low_score_plain_risk_on_cap.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": scout.base.WINDOWS,
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
                "portfolio_engine strategy",
                "portfolio_engine regime_exit_bucket",
                "portfolio_engine risk_on_unmodified_risk_multiplier_applied",
                "portfolio_engine spy_relative_leader_risk_on_multiplier_applied",
                "portfolio_engine sizing entry_price",
                "portfolio_engine sizing net_risk_per_share",
                "portfolio_engine sizing base_risk_pct",
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
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "sweep_summary": scout._sweep_summary(sweep_results),
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the low-score plain risk-on cap through shared portfolio_engine.size_signals, include the attribution key in backtester.py, and add focused production/backtest parity tests before live orders change."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "decision_reason": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote only through shared sizing code and parity tests."
            if selected["passed"]
            else "Do not retry nearby low-score plain risk-on cap values without forward cap-room evidence or a new production-visible discriminator."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        scout.base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        scout.base.REPO_ROOT
        / "experiments"
        / "logs"
        / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        scout.base.REPO_ROOT
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        scout.base.REPO_ROOT
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
        "artifact": str(artifact_path.relative_to(scout.base.REPO_ROOT)),
        "log": str(log_path.relative_to(scout.base.REPO_ROOT)),
    }
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(payload["artifact_markdown"] + "\n", encoding="utf-8")
    _upsert_jsonl(scout.base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_max_position_pct": result["parameters"][
                    "selected_max_position_pct"
                ],
                "gate4": result["gate4"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "sweep_summary": result["sweep_summary"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
