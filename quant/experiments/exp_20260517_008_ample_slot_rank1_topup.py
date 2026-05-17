"""exp-20260517-008: ample-slot rank-1 cap-aware top-up scout.

Tests one production-visible allocation state on the accepted core stack:
when the shared entry planner has at least four available slots, apply a small
cap-aware top-up only to the already-selected rank-1 signal.

This is replay-only. A positive result must be promoted through shared
``production_parity.py`` policy plus parity tests before production behavior
changes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import production_parity as production_parity_module


EXPERIMENT_ID = "exp-20260517-008"
EXPERIMENT_SLUG = "ample_slot_rank1_topup"
MULTIPLIER_KEY = "ample_slot_rank1_risk_multiplier_applied"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [1.0, 1.0125, 1.025, 1.05]
AVAILABLE_SLOTS_MIN = 4
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 8
MIN_AFFECTED_WINDOW_COUNT = 2
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

CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER


def _make_passthrough_wrapper(original):
    return original


def _apply_ample_slot_topup(signals: list[dict[str, Any]], available_slots: int):
    if (
        available_slots < AVAILABLE_SLOTS_MIN
        or not signals
        or CURRENT_RISK_MULTIPLIER <= 1.0
    ):
        return signals, []

    planned = list(signals)
    sig = dict(planned[0])
    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return signals, []

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or portfolio_value <= 0 or net_risk_per_share <= 0:
        return signals, []

    cap_pct = float(
        sizing.get("max_position_pct_applied")
        or production_parity_module.MAX_POSITION_PCT
    )
    desired_shares = max(
        old_shares,
        int(math.floor(old_shares * CURRENT_RISK_MULTIPLIER)),
    )
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= old_shares:
        return signals, []

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value
    sizing["ample_slot_rank1_state"] = True
    sizing["ample_slot_rank1_available_slots"] = available_slots
    sizing["ample_slot_rank1_baseline_shares"] = old_shares
    sizing["ample_slot_rank1_desired_shares"] = desired_shares
    sizing["ample_slot_rank1_cap_shares"] = cap_shares
    sizing["ample_slot_rank1_new_shares"] = new_shares
    sizing[MULTIPLIER_KEY] = CURRENT_RISK_MULTIPLIER
    sig["sizing"] = sizing
    planned[0] = sig

    adjustment = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector", "Unknown"),
        "available_slots": available_slots,
        "candidate_rank": 1,
        "baseline_shares": old_shares,
        "desired_shares": desired_shares,
        "cap_shares": cap_shares,
        "new_shares": new_shares,
        "multiplier": CURRENT_RISK_MULTIPLIER,
        "trade_quality_score": sig.get("trade_quality_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "regime_exit_score": sig.get("regime_exit_score"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "signal_day_ticker_green_candle": sig.get(
            "signal_day_ticker_green_candle"
        ),
        "signal_day_ticker_outperformed_spy": sig.get(
            "signal_day_ticker_outperformed_spy"
        ),
        "price_vs_200ma_extension_state": sig.get(
            "price_vs_200ma_extension_state"
        ),
    }
    base.ADJUSTMENTS.append(adjustment)
    return planned, [adjustment]


def _make_scarce_slot_wrapper(original):
    def wrapped(signals, available_slots, multiplier=None):
        if available_slots >= AVAILABLE_SLOTS_MIN:
            return _apply_ample_slot_topup(signals, available_slots)
        return original(signals, available_slots, multiplier=multiplier)

    return wrapped


def _run_window_with_multiplier(label: str, multiplier: float) -> dict[str, Any]:
    global CURRENT_RISK_MULTIPLIER
    CURRENT_RISK_MULTIPLIER = multiplier
    original_topup = production_parity_module._apply_scarce_slot_rank1_topup
    production_parity_module._apply_scarce_slot_rank1_topup = _make_scarce_slot_wrapper(
        original_topup
    )
    try:
        return base._run_window(label, variant=True)
    finally:
        production_parity_module._apply_scarce_slot_rank1_topup = original_topup


def _apply_gate4_guards(candidate: dict[str, Any]) -> dict[str, Any]:
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in candidate["delta_metrics"]["by_window"].values()
    )
    affected_windows = [
        label for label, rows in candidate["adjustments"].items() if rows
    ]
    sample_guard_passed = (
        candidate["gate4"]["affected_signal_count"] >= MIN_AFFECTED_SIGNAL_COUNT
        and len(affected_windows) >= MIN_AFFECTED_WINDOW_COUNT
    )
    drawdown_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    candidate["gate4"]["affected_windows"] = affected_windows
    candidate["gate4"]["minimum_affected_signal_count"] = MIN_AFFECTED_SIGNAL_COUNT
    candidate["gate4"]["minimum_affected_window_count"] = MIN_AFFECTED_WINDOW_COUNT
    candidate["gate4"]["sample_guard_passed"] = sample_guard_passed
    candidate["gate4"]["max_drawdown_worse"] = round(max_drawdown_worse, 6)
    candidate["gate4"]["max_drawdown_worse_guardrail"] = (
        MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    candidate["gate4"]["drawdown_guardrail_passed"] = drawdown_passed
    candidate["passed"] = (
        bool(candidate["passed"])
        and sample_guard_passed
        and drawdown_passed
        and not candidate["is_identity_control"]
    )
    candidate["gate4"]["passed"] = candidate["passed"]
    return candidate


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        variant = _run_window_with_multiplier(label, multiplier)
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
    affected_count = sum(len(rows) for rows in adjustments.values())
    is_identity = math.isclose(multiplier, BASELINE_RISK_MULTIPLIER)
    passed = (
        not is_identity
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and affected_count > 0
    )
    return _apply_gate4_guards(
        {
            "risk_multiplier": multiplier,
            "is_identity_control": is_identity,
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
                "affected_signal_count": affected_count,
            },
            "adjustments": adjustments,
            "changed_trades": changed_trades,
            "sizing_attribution": sizing_attribution,
            "expected_value_score_delta": aggregate_delta[
                "expected_value_score_sum"
            ],
            "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        }
    )


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    non_identity = [row for row in candidates if not row["is_identity_control"]]
    passed = [row for row in non_identity if row["passed"]]
    pool = passed if passed else non_identity
    return max(
        pool,
        key=lambda row: (
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"].get("max_drawdown_worse") or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        rows.append(
            {
                "risk_multiplier": row["risk_multiplier"],
                "is_identity_control": row["is_identity_control"],
                "passed": row["passed"],
                "expected_value_score_delta": row["expected_value_score_delta"],
                "total_pnl_delta": row["total_pnl_delta"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "affected_signal_count": row["gate4"]["affected_signal_count"],
                "affected_windows": row["gate4"]["affected_windows"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
                "sample_guard_passed": row["gate4"]["sample_guard_passed"],
                "drawdown_guardrail_passed": row["gate4"][
                    "drawdown_guardrail_passed"
                ],
            }
        )
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                windows=", ".join(row["affected_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Ample-Slot Rank-1 Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-selection top-up on the already-selected rank-1 signal when the shared entry planner has at least four available slots. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.",
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
            "Production impact: replay-only scout. A positive promotion must implement this in shared `production_parity.py`, add parity tests, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_modules() -> None:
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_passthrough_wrapper
    base._make_enrich_wrapper = _make_passthrough_wrapper
    base._make_size_wrapper = _make_passthrough_wrapper
    base._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: _run_window_with_multiplier(label, BASELINE_RISK_MULTIPLIER)
        for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_ample_slot_rank1_topup"
    )
    interpretation = (
        "The ample-slot rank-1 top-up cleared the canonical three-window scout and requires shared production_parity promotion plus rerun before production use."
        if selected["passed"]
        else "Top-ranked entries in the ample-slot state should not receive a standalone cap-aware top-up on the frozen three-window evidence."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Recent LLM/SEC semantic ranking remains field-limited, DTE pockets "
            "are sample-thin, and two-slot scarce-capital top-ups failed. The next "
            "production-visible allocation state worth testing is the opposite "
            "slot regime: when at least four entry slots are open, the already "
            "selected rank-1 signal may deserve a small cap-aware top-up because "
            "it does not crowd out a scarce replacement candidate."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "ample_slot_rank1_risk_multiplier",
        "single_causal_variable": (
            "post-selection cap-aware top-up on candidate_rank=1 when available_slots >= 4"
        ),
        "parameters": {
            "state_definition": {
                "available_slots_min": AVAILABLE_SLOTS_MIN,
                "candidate_rank": 1,
                "already_selected_only": True,
                "cap_aware": True,
            },
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "candidate pool",
                "stop and target logic",
                "all existing sizing multipliers",
                "one-slot rank-1 top-up",
                "portfolio heat",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation on a production-visible ample-slot rank-1 "
                "state; this follows the playbook preference for fixed-candidate "
                "allocation while avoiding exhausted LLM/SEC, DTE, and two-slot "
                "branches"
            ),
            "2_history_check": {
                "exp-20260517-004": (
                    "Accepted available_slots == 1 rank-1 top-up; this does not "
                    "broaden scarce-slot sizing and instead tests the opposite "
                    "ample-slot regime."
                ),
                "exp-20260517-005_and_006": (
                    "Rejected available_slots == 2 rank-1/rank-2 top-ups; this "
                    "avoids two-slot scarce-capital broadening."
                ),
                "exp-20260517-007": (
                    "Financials DTE scalar had positive directional deltas but "
                    "was sample-limited; this uses a broader runtime state with "
                    "expected cross-window sample coverage."
                ),
            },
            "3_single_causal_variable": (
                "ample_slot_rank1_risk_multiplier applied only after shared "
                "candidate selection when available_slots >= 4"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
                "at least eight affected signals across at least two windows, and max drawdown "
                "drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260517_008_ample_slot_rank1_topup.py"
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
                "production_parity plan_entry_candidates available_slots",
                "production_parity slot-sliced rank order",
                "sizing shares_to_buy",
                "sizing entry_price",
                "sizing portfolio_value_usd",
                "sizing net_risk_per_share",
                "sizing max_position_pct_applied",
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
                "this deterministic allocation state avoids those blockers."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the ample-slot top-up to shared production_parity.py "
                "used by both backtester.py and quant/run.py, add parity tests, and "
                "rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC branches because PIT semantic attribution is still "
            "insufficient, avoids the sample-thin Financials DTE pocket, avoids "
            "nearby two-slot scarce-capital top-ups after Gate 4 failures, and "
            "does not expand the candidate pool."
        ),
        "known_risks": [
            "The state uses slot availability, so it must not be interpreted as a broad capacity or max-position sweep.",
            "Ample-slot rank-1 winners may already be near cap-bound, limiting actual share changes.",
            "A positive replay scout is not production-tradable until shared production_parity code and tests are promoted and rerun.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry slot-availability top-ups without a materially different production-visible discriminator."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260517_008_ample_slot_rank1_topup.py",
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
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "affected_windows": result["gate4"]["affected_windows"],
                "selected_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
