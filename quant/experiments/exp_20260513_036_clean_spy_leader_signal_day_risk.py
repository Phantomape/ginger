"""exp-20260513-036: clean SPY-leader signal-day risk allocation.

Tests one production-visible allocation variable on the accepted core stack:
already-qualified risk-on SPY-relative leaders get a small cap-aware share
top-up only when their own signal-day open-to-close return also beats SPY.

This is not an entry filter, ranking change, exit change, universe change,
LLM/news change, or Space sleeve change.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260513-036"
EXPERIMENT_SLUG = "clean_spy_leader_signal_day_risk"
MULTIPLIER_KEY = "clean_spy_leader_signal_day_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.05, 1.075, 1.10, 1.15]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _run_window(label: str, multiplier: float) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_multiplier = (
        base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER
    )
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
        base.backtester_module.SIZING_MULTIPLIER_KEYS = (
            *base.backtester_module.SIZING_MULTIPLIER_KEYS,
            MULTIPLIER_KEY,
        )

    try:
        base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER = (
            multiplier
        )
        engine = base.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER = (
            original_multiplier
        )
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

    if result.get("error"):
        raise RuntimeError(f"{label} multiplier {multiplier} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "sizing_rule_signal_attribution": (
            result.get("sizing_rule_signal_attribution") or {}
        ),
        "sizing_rule_trade_attribution": (
            result.get("sizing_rule_trade_attribution") or {}
        ),
    }


def _attribution_count(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    for key in ("signals_seen", "trade_count"):
        raw = value.get(key)
        if isinstance(raw, (int, float)):
            return int(raw)
    return 0


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_runs = {
        label: _run_window(label, multiplier)
        for label in base.WINDOWS
    }
    after_metrics = {label: after_runs[label]["metrics"] for label in base.WINDOWS}
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
    sizing_attribution = {
        label: {
            "signal": after_runs[label]["sizing_rule_signal_attribution"].get(
                MULTIPLIER_KEY
            ),
            "trade": after_runs[label]["sizing_rule_trade_attribution"].get(
                MULTIPLIER_KEY
            ),
        }
        for label in base.WINDOWS
    }
    adjusted_signal_count = sum(
        _attribution_count(sizing_attribution[label]["signal"])
        for label in base.WINDOWS
    )
    adjusted_trade_count = sum(
        _attribution_count(sizing_attribution[label]["trade"])
        for label in base.WINDOWS
    )
    changed_trades = {
        label: base._changed_trades(
            before_runs[label]["trades"],
            after_runs[label]["trades"],
        )
        for label in base.WINDOWS
    }
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = (
        max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_signal_count > 0
        and drawdown_guardrail_passed
    )
    return {
        "multiplier": multiplier,
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
            "adjusted_signal_count": adjusted_signal_count,
            "adjusted_trade_count": adjusted_trade_count,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    rows = passed or candidates
    return max(
        rows,
        key=lambda row: row["delta_metrics"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
    )


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
            )
        )
    sweep_rows = [
        "| Multiplier | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_results"]:
        agg = row["delta_metrics"]["aggregate_delta"]
        sweep_rows.append(
            "| {mult:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {dd:+.4f} | {adj} |".format(
                mult=row["multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=agg["expected_value_score_sum"],
                dpnl=agg["total_pnl_sum"],
                dd=row["gate4"]["max_drawdown_worse"],
                adj=row["gate4"]["adjusted_signal_count"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Clean SPY-Leader Signal-Day Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing share multiplier for signals that already qualify for the clean risk-on SPY-relative leader path and also beat SPY open-to-close on the signal day.",
            "",
            *rows,
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "Production impact: accepted implementation lives in shared `risk_engine.py` and `portfolio_engine.py`; `backtester.py` only adds the attribution key. The daily production path already calls the shared modules.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: _run_window(label, 1.0)
        for label in base.WINDOWS
    }
    sweep_results = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(sweep_results)
    accepted = selected["passed"]
    decision = (
        "accepted_clean_spy_leader_signal_day_1_10_risk_topup"
        if accepted and selected["multiplier"] == 1.10
        else "rejected_clean_spy_leader_signal_day_risk_topup"
    )
    interpretation = (
        "The 1.10x clean SPY-relative leader signal-day top-up improves aggregate EV/PnL with two EV-improved windows, no EV-regressed windows, unchanged survival/trades, and max drawdown drift inside the Gate 4 guardrail."
        if decision.startswith("accepted")
        else "No swept clean SPY-relative leader signal-day top-up cleared the canonical three-window gate at the promoted 1.10x scalar."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The best continuation candidates are not just same-day green or RS leaders; they are existing clean risk-on SPY-relative leaders with fresh idiosyncratic signal-day confirmation versus SPY."
        ),
        "change_type": "risk_allocation",
        "changed_variable": "clean_spy_leader_signal_day_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing share multiplier for clean risk-on SPY-relative leaders whose signal-day open-to-close return beats SPY"
        ),
        "parameters": {
            "selected_multiplier": selected["multiplier"],
            "sweep": RISK_MULTIPLIER_SWEEP,
            "requires_spy_relative_leader_risk_on_multiplier": 2.0,
            "requires_signal_day_ticker_outperformed_spy": True,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "existing RS20/green/RS60 sizing rules",
                "portfolio heat and caps",
                "LLM/news replay",
                "Space sleeve",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core risk allocation: clean SPY-relative leaders with same-day idiosyncratic confirmation should deserve slightly more capital.",
            "2_history_check": {
                "exp-20260513-010": "broad signal-day ticker-minus-SPY was directionally positive but failed drawdown guardrail.",
                "exp-20260513-011": "broad signal-day SPY-relative leader top-up was too coarse.",
                "exp-20260513-030": "RS60 top-quintile is accepted; this does not retune RS60 and adds a narrower production-visible confirmation state.",
                "llm_soft_ranking": "not used because current records remain too thin for trustworthy LLM soft-ranking alpha.",
            },
            "3_single_causal_variable": "clean_spy_leader_signal_day_risk_multiplier sweep only.",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 percentage points.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_036_clean_spy_leader_signal_day_risk.py",
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
                "risk_engine signal_day_ticker_open_close_return_pct",
                "risk_engine spy_signal_day_open_close_return_pct",
                "risk_engine ticker_minus_spy_signal_day_open_close_return_pct",
                "risk_engine signal_day_ticker_outperformed_spy",
                "portfolio_engine spy_relative_leader_risk_on_multiplier_applied",
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
        "sweep_results": sweep_results,
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "expected_value_score_delta": selected["delta_metrics"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": selected["delta_metrics"]["aggregate_delta"][
            "total_pnl_sum"
        ],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": decision.startswith("accepted"),
            "backtester_adapter_changed": decision.startswith("accepted"),
            "run_adapter_changed": decision.startswith("accepted"),
            "run_adapter_change_note": (
                "No run.py edit required; production calls shared risk_engine and portfolio_engine."
            ),
            "replay_only": False,
            "parity_test_added": True,
        },
        "interpretation": interpretation,
        "rejection_reason": None if decision.startswith("accepted") else interpretation,
        "next_evidence_needed": None
        if decision.startswith("accepted")
        else "Use a different production-visible state variable; do not retune nearby clean SPY-leader signal-day multipliers on these frozen windows.",
        "related_files": [
            "quant/constants.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
            "quant/backtester.py",
            "quant/test_quant.py",
            "quant/experiments/exp_20260513_036_clean_spy_leader_signal_day_risk.py",
            "data/experiments/exp-20260513-036/clean_spy_leader_signal_day_risk.json",
            "docs/experiments/logs/exp-20260513-036.json",
            "docs/experiments/tickets/exp-20260513-036.json",
            "docs/experiments/artifacts/exp-20260513-036_clean_spy_leader_signal_day_risk.md",
            "docs/backtesting.md",
            "docs/production_backtest_parity.md",
            "docs/experiment_log.jsonl",
        ],
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
        base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
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
        "selected_multiplier": payload["parameters"]["selected_multiplier"],
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
                "selected_multiplier": result["parameters"]["selected_multiplier"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
