"""exp-20260516-018: core confirmed-quality cap release scout."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260516-018"
EXPERIMENT_SLUG = "core_confirmed_quality_cap"
CAP_KEY = "core_confirmed_quality_max_position_pct_applied"
RATIO_KEY = "core_confirmed_quality_cap_release_multiplier_applied"
CAP_SWEEP = [0.425, 0.45, 0.475, 0.50]
CURRENT_MAX_POSITION_PCT = CAP_SWEEP[0]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_ADJUSTED_SIGNAL_COUNT = 3
MIN_ADJUSTED_WINDOW_COUNT = 2
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}


def _cap_release_sizing(
    sizing: dict[str, Any],
    cap_pct: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    entry = float(sizing.get("entry_price") or 0.0)
    if shares <= 0 or entry <= 0 or portfolio_value <= 0:
        return sizing

    desired = int(sizing.get("core_confirmed_quality_desired_shares") or shares)
    cap_shares = int(math.floor((portfolio_value * cap_pct) / entry))
    new_shares = max(1, min(desired, cap_shares))
    if new_shares <= shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["core_confirmed_quality_cap_baseline_shares"] = shares
    out["core_confirmed_quality_cap_desired_shares"] = desired
    out["core_confirmed_quality_cap_new_cap_shares"] = cap_shares
    out["core_confirmed_quality_cap_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = round((entry * new_shares) / portfolio_value, 4)
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (net_risk_per_share * new_shares) / portfolio_value
    out[CAP_KEY] = cap_pct
    out[RATIO_KEY] = round(new_shares / shares, 6)
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
            if sig.get("core_confirmed_quality_state") is True and sizing.get("shares_to_buy"):
                adjusted = _cap_release_sizing(
                    sizing,
                    CURRENT_MAX_POSITION_PCT,
                    portfolio_value,
                )
                if adjusted is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted.get("shares_to_buy"),
                            "cap_pct": CURRENT_MAX_POSITION_PCT,
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "core_confirmed_quality_state": sig.get(
                                "core_confirmed_quality_state"
                            ),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                        }
                    )
                    sig = {**sig, "sizing": adjusted}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, *, variant: bool) -> dict[str, Any]:
    original_make_size = base._make_size_wrapper
    original_multiplier_key = base.MULTIPLIER_KEY
    original_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS
    base.WINDOWS = WINDOWS
    if variant:
        base._make_size_wrapper = _make_size_wrapper
        base.MULTIPLIER_KEY = RATIO_KEY
        if RATIO_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                RATIO_KEY,
            )
    try:
        return base._run_window(label, variant=variant)
    finally:
        base._make_size_wrapper = original_make_size
        base.MULTIPLIER_KEY = original_multiplier_key
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_keys


def _candidate_payload(
    cap_pct: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    global CURRENT_MAX_POSITION_PCT
    CURRENT_MAX_POSITION_PCT = cap_pct

    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in WINDOWS:
        variant = _run_window(label, variant=True)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(RATIO_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(RATIO_KEY),
        }

    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    adjusted_windows = [label for label, rows in adjustments.items() if rows]
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in by_window_delta.values()
    )
    sample_guard_passed = (
        adjusted_count >= MIN_ADJUSTED_SIGNAL_COUNT
        and len(adjusted_windows) >= MIN_ADJUSTED_WINDOW_COUNT
    )
    drawdown_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and sample_guard_passed
        and drawdown_passed
    )
    return {
        "cap_pct": cap_pct,
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
            "adjusted_windows": adjusted_windows,
            "minimum_adjusted_signal_count": MIN_ADJUSTED_SIGNAL_COUNT,
            "minimum_adjusted_window_count": MIN_ADJUSTED_WINDOW_COUNT,
            "sample_guard_passed": sample_guard_passed,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_passed,
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
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"].get("max_drawdown_worse") or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cap_pct": row["cap_pct"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "adjusted_windows": row["gate4"]["adjusted_windows"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "sample_guard_passed": row["gate4"]["sample_guard_passed"],
            "drawdown_guardrail_passed": row["gate4"]["drawdown_guardrail_passed"],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Windows | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {cap:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {windows} | {dd:+.4f} |".format(
                cap=row["cap_pct"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                windows=", ".join(row["adjusted_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )
    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
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
            f"# {EXPERIMENT_ID} Core Confirmed-Quality Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: single-position cap for already-qualified `core_confirmed_quality_state=true` signals. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
        ]
    )


def run() -> dict[str, Any]:
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base._markdown = _markdown
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, variant=False) for label in WINDOWS}
    candidates = [_candidate_payload(cap, before_runs) for cap in CAP_SWEEP]
    selected = _select_candidate(candidates)
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_core_confirmed_quality_cap"
    )
    interpretation = (
        "Core confirmed-quality cap release cleared the canonical three-window scout and requires shared policy implementation before production use."
        if selected["passed"]
        else "Core confirmed-quality cap release did not clear Gate 4; do not add another cap-room rule to this accepted state on frozen windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted core_confirmed_quality state may be under-allocated "
            "when default 40% single-position caps truncate cap-aware top-ups. "
            "A narrow cap release should improve EV if the state has genuine "
            "replacement value beyond its current risk scalar."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "core_confirmed_quality_max_position_pct",
        "single_causal_variable": (
            "single-position cap for core_confirmed_quality_state=True signals"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "selected_cap_pct": selected["cap_pct"],
            "state_definition": {"core_confirmed_quality_state": True},
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_adjusted_signal_count": MIN_ADJUSTED_SIGNAL_COUNT,
            "minimum_adjusted_window_count": MIN_ADJUSTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation on accepted core candidates; tests cap-room "
                "rather than another scalar retune or filter"
            ),
            "2_history_check": {
                "exp-20260515-028": (
                    "accepted the core_confirmed_quality risk scalar; no prior "
                    "run isolated a cap release for that exact accepted state"
                ),
                "exp-20260516-002": (
                    "confirmed-quality slot priority failed, so this run does not "
                    "change ordering or replacement; it only tests position cap-room"
                ),
                "recent cap rules": (
                    "cap releases worked only when tied to already-winning states; "
                    "this run uses an accepted state and a sweep instead of a fixed guess"
                ),
            },
            "3_single_causal_variable": "core_confirmed_quality_max_position_pct",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
                "at least three adjusted signals across at least two windows, and max "
                "drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_018_core_confirmed_quality_cap.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
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
                "risk_engine core_confirmed_quality_state",
                "portfolio_engine core_confirmed_quality_desired_shares",
                "portfolio_engine shares_to_buy",
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
            "blocker_relation": (
                "LLM soft-ranking and SEC semantic branches remain data-limited; "
                "this deterministic cap-room state avoids those blockers."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the exact cap state in shared "
                "portfolio_engine.py, expose the attribution key in both adapters, "
                "add focused parity tests, and rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC branches because PIT semantic attribution is "
            "still insufficient, avoids Space/event-sleeve retunes because recent "
            "positives are default-off and sample constrained, avoids broad ticker "
            "pool growth, and avoids changing candidate priority after "
            "confirmed-quality slot priority failed."
        ),
        "known_risks": [
            "Cap releases can raise concentration and drawdown faster than scalar top-ups.",
            "A positive replay scout is not production-tradable until shared policy and parity tests exist.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry nearby confirmed-quality cap values on these frozen windows without forward cap-room attribution or a materially different state."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_018_core_confirmed_quality_cap.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> dict[str, Any]:
    result = run()
    base.persist(result)
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
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "adjusted_windows": result["gate4"]["adjusted_windows"],
                "selected_cap_pct": result["parameters"]["selected_cap_pct"],
            },
            indent=2,
            sort_keys=True,
        )
    )
