"""exp-20260513-029: Space leave-one-out peer momentum state.

Tests one causal variable on top of the accepted exp-20260513-028 default-off
Space stack: define peer leadership against the equal-weight official Space
peer basket excluding the ticker itself, instead of against the official Space
basket average that includes the ticker. This is a relative-strength alpha
definition test, not LLM soft-ranking, candidate-pool expansion, or scalar
retuning.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from exp_20260511_115_space_basket_momentum_risk import (  # noqa: E402
    PROJECT_ROOT,
    WINDOWS,
    _aggregate_delta,
    _delta,
    _gate2_open_positions,
    _run_core_baseline,
    _safe,
    _write_json,
)
from exp_20260513_028_space_single_event_defense_haircut import (  # noqa: E402
    ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
    _accepted_financing_profile_gate,
    _event_seed_profiles,
    _field_check_company_release_source,
    _field_check_government_contract_profile,
    _field_check_iwm_peer_leader_trend,
    _field_check_multi_event_depth,
    _field_check_peer_leader_state,
    _field_check_single_event_defense_profile,
    _field_check_watch_liquidity_tier,
    _run_variant as _run_exp028_variant,
)


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-029"
STEM = "space_leave_one_out_peer_state"
ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR = 1.05

_ORIGINAL_REFERENCE_PEER_STATE: Callable[[dict[str, Any]], dict[str, Any]] | None = None
_LEAVE_ONE_OUT_DIAGNOSTICS: dict[str, Any] = {}


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _round(value: Any, ndigits: int = 6) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return round(out, ndigits)


def _reset_leave_one_out_diagnostics() -> None:
    _LEAVE_ONE_OUT_DIAGNOSTICS.clear()
    _LEAVE_ONE_OUT_DIAGNOSTICS.update(
        {
            "evaluated_signal_count": 0,
            "with_own_value_count": 0,
            "with_peer_values_count": 0,
            "missing_peer_values_count": 0,
            "state_changed_count": 0,
            "old_state_counts": Counter(),
            "new_state_counts": Counter(),
            "sample_state_changes": [],
        }
    )


def _leave_one_out_diagnostics_snapshot() -> dict[str, Any]:
    out = deepcopy(_LEAVE_ONE_OUT_DIAGNOSTICS)
    out["old_state_counts"] = dict(sorted(out["old_state_counts"].items()))
    out["new_state_counts"] = dict(sorted(out["new_state_counts"].items()))
    return out


def _leave_one_out_peer_momentum_state(signal: dict[str, Any]) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    values = signal.get("space_basket_momentum_values") or {}
    own = _round(values.get(ticker), 6)
    peer_values = [
        _round(value, 6)
        for raw_ticker, value in values.items()
        if str(raw_ticker or "").upper() != ticker
    ]
    peer_values = [value for value in peer_values if value is not None]

    _LEAVE_ONE_OUT_DIAGNOSTICS["evaluated_signal_count"] += 1
    if own is not None:
        _LEAVE_ONE_OUT_DIAGNOSTICS["with_own_value_count"] += 1
    if peer_values:
        _LEAVE_ONE_OUT_DIAGNOSTICS["with_peer_values_count"] += 1
    else:
        _LEAVE_ONE_OUT_DIAGNOSTICS["missing_peer_values_count"] += 1

    old_state: dict[str, Any] | None = None
    if _ORIGINAL_REFERENCE_PEER_STATE is not None:
        old_state = _ORIGINAL_REFERENCE_PEER_STATE(signal)
        _LEAVE_ONE_OUT_DIAGNOSTICS["old_state_counts"][
            str(old_state.get("state") or "unknown")
        ] += 1

    if own is None or not peer_values:
        result = {
            "state": "missing",
            "own_momentum_20d_pct": own,
            "basket_momentum_20d_pct": None,
            "excess_momentum_20d_pct": None,
        }
    else:
        peer_average = _round(sum(peer_values) / len(peer_values), 6)
        excess = _round(own - peer_average, 6)
        result = {
            "state": "leader" if excess is not None and excess > 0 else "nonleader",
            "own_momentum_20d_pct": own,
            "basket_momentum_20d_pct": peer_average,
            "excess_momentum_20d_pct": excess,
        }

    new_state = str(result.get("state") or "unknown")
    _LEAVE_ONE_OUT_DIAGNOSTICS["new_state_counts"][new_state] += 1
    if old_state is not None and str(old_state.get("state")) != new_state:
        _LEAVE_ONE_OUT_DIAGNOSTICS["state_changed_count"] += 1
        samples = _LEAVE_ONE_OUT_DIAGNOSTICS["sample_state_changes"]
        if len(samples) < 20:
            samples.append(
                {
                    "ticker": ticker,
                    "old_state": old_state.get("state"),
                    "new_state": new_state,
                    "old_basket_momentum_20d_pct": old_state.get(
                        "basket_momentum_20d_pct"
                    ),
                    "leave_one_out_peer_momentum_20d_pct": result.get(
                        "basket_momentum_20d_pct"
                    ),
                    "own_momentum_20d_pct": own,
                    "old_excess_momentum_20d_pct": old_state.get(
                        "excess_momentum_20d_pct"
                    ),
                    "leave_one_out_excess_momentum_20d_pct": result.get(
                        "excess_momentum_20d_pct"
                    ),
                }
            )
    return result


def _patch_peer_state(
    replacement: Callable[[dict[str, Any]], dict[str, Any]]
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    originals: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith("exp_"):
            continue
        current = getattr(module, "_peer_momentum_state", None)
        if callable(current):
            originals[name] = current
            setattr(module, "_peer_momentum_state", replacement)
    return originals


def _restore_peer_state(
    originals: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]
) -> None:
    for name, original in originals.items():
        module = sys.modules.get(name)
        if module is not None:
            setattr(module, "_peer_momentum_state", original)


def _build_field_gates() -> dict[str, Any]:
    gates = {
        "open_positions": _gate2_open_positions(),
        "official_customer_source_profile": _event_seed_profiles(),
        "accepted_financing_dilution_profiles": _accepted_financing_profile_gate(),
        "accepted_company_release_source_profile": _field_check_company_release_source(),
        "watch_liquidity_tier_registry": _field_check_watch_liquidity_tier(),
        "accepted_multi_event_depth": _field_check_multi_event_depth(),
        "government_contract_profile": _field_check_government_contract_profile(),
        "single_event_defense_profile": _field_check_single_event_defense_profile(),
    }
    gates["passed"] = all(bool(row.get("passed")) for row in gates.values())
    return gates


def _run_accepted_exp028_stack(name: str, gates: dict[str, Any]) -> dict[str, Any]:
    return _run_exp028_variant(
        name,
        ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
        gates["single_event_defense_profile"],
        gates["government_contract_profile"],
        gates["official_customer_source_profile"],
        gates["accepted_multi_event_depth"],
        gates["watch_liquidity_tier_registry"],
        gates["accepted_company_release_source_profile"],
        gates["accepted_financing_dilution_profiles"],
    )


def _peer_dependent_adjustment_delta(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    keys = (
        "space_iwm_peer_leader_trend_adjustment",
        "space_government_contract_peer_leader_adjustment",
        "space_customer_source_peer_leader_adjustment",
        "space_peer_nonleader_breakout_adjustment",
    )
    by_window: dict[str, Any] = {}
    total_abs_delta = 0
    for label in WINDOWS:
        row: dict[str, Any] = {}
        for key in keys:
            before_count = int(
                (before["by_window"][label].get(key) or {}).get(
                    "adjusted_signal_count", 0
                )
            )
            after_count = int(
                (after["by_window"][label].get(key) or {}).get(
                    "adjusted_signal_count", 0
                )
            )
            delta = after_count - before_count
            total_abs_delta += abs(delta)
            row[key] = {
                "before_adjusted_signal_count": before_count,
                "after_adjusted_signal_count": after_count,
                "delta": delta,
            }
        by_window[label] = row
    return {
        "by_window": by_window,
        "total_abs_adjusted_signal_count_delta": total_abs_delta,
    }


def _gate(
    after: dict[str, Any],
    before: dict[str, Any],
    core: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(after["aggregate"], before["aggregate"])
    aggregate_delta_vs_core = _aggregate_delta(after["aggregate"], core["aggregate"])
    by_window_delta = {
        label: _delta(after["by_window"][label]["metrics"], before["by_window"][label]["metrics"])
        for label in WINDOWS
    }
    windows_ev_improved = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) > 0
    )
    windows_ev_regressed = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) < 0
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and after["aggregate"]["min_survival_rate"] >= 0.05
        and after["aggregate"]["trade_count_sum"] >= 50
        and int(diagnostics["state_changed_count"]) > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "min_survival_rate_after": after["aggregate"]["min_survival_rate"],
        "trade_count_sum_after": after["aggregate"]["trade_count_sum"],
        "peer_state_changed_count": diagnostics["state_changed_count"],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space leave-one-out peer state",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV delta: `{payload['expected_value_score_delta']:+.4f}`",
        f"- aggregate PnL delta: `${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`",
        f"- peer-state changes: `{payload['leave_one_out_diagnostics']['state_changed_count']}`",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} |".format(
                label=label,
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before["total_pnl"],
                after_pnl=after["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after["trade_count"],
                max_dd=after["max_drawdown_pct"],
                survival=after["survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Gate 2",
            "",
            json.dumps(payload["gate2"], sort_keys=True),
            "",
            "## Peer-State Diagnostics",
            "",
            json.dumps(payload["leave_one_out_diagnostics"], sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], sort_keys=True),
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    gates = _build_field_gates()
    if not gates["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gates}")

    core = _run_core_baseline()
    before = _run_accepted_exp028_stack("accepted_exp028_stack", gates)
    gates["peer_momentum_state"] = _field_check_peer_leader_state(before)
    gates["iwm_peer_leader_trend_state"] = _field_check_iwm_peer_leader_trend(before)
    gates["passed"] = gates["passed"] and gates["peer_momentum_state"][
        "passed"
    ] and gates["iwm_peer_leader_trend_state"]["passed"]
    if not gates["passed"]:
        raise RuntimeError(f"Peer/IWM field check failed: {gates}")

    global _ORIGINAL_REFERENCE_PEER_STATE
    originals = _patch_peer_state(_leave_one_out_peer_momentum_state)
    if not originals:
        raise RuntimeError("No experiment modules with _peer_momentum_state were patched")
    _ORIGINAL_REFERENCE_PEER_STATE = next(iter(originals.values()))
    _reset_leave_one_out_diagnostics()
    try:
        after = _run_accepted_exp028_stack("leave_one_out_peer_state", gates)
    finally:
        _restore_peer_state(originals)
        _ORIGINAL_REFERENCE_PEER_STATE = None

    diagnostics = _leave_one_out_diagnostics_snapshot()
    peer_adjustment_delta = _peer_dependent_adjustment_delta(before, after)
    gate4 = _gate(after, before, core, diagnostics)
    accepted = bool(gate4["passed"])
    decision = (
        "accepted_default_off_space_leave_one_out_peer_state"
        if accepted
        else "rejected_space_leave_one_out_peer_state"
    )
    interpretation = (
        "Leave-one-out peer-state cleared the three-window gate on top of the "
        "accepted exp-028 default-off Space stack. The change tightens relative "
        "strength attribution by removing self-contamination from the peer "
        "benchmark, and should be promoted only through shared Space policy so "
        "replay and production observation use the same definition."
        if accepted
        else (
            "Leave-one-out peer-state did not clear the three-window gate on top "
            "of the accepted exp-028 Space stack. The peer benchmark definition "
            "changed excess magnitudes but no leader/nonleader classifications, "
            "so the accepted state-based peer helpers were behaviorally unchanged."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_peer_state_definition",
        "changed_variable": "space_peer_momentum_state_definition",
        "single_causal_variable": (
            "Space peer leadership benchmark changes from own 20d momentum versus "
            "official Space basket average including own ticker to own 20d momentum "
            "versus equal-weight official Space peers excluding own ticker."
        ),
        "hypothesis": (
            "Relative-strength helpers should measure replacement value versus "
            "other official Space candidates, not versus a basket statistic that "
            "partly contains the same ticker. A leave-one-out peer benchmark may "
            "better separate actual peer leaders from self-contaminated leaders."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / ranking boundary: redefine Space peer leader "
                "state as own 20d momentum above official peer average excluding "
                "the ticker itself. This follows the playbook direction of "
                "catalyst-quality plus relative-strength allocation."
            ),
            "2_history_check": {
                "exp-20260513-014": (
                    "Accepted customer-source peer-leader risk using the old "
                    "full-basket peer-state definition."
                ),
                "exp-20260513-015": (
                    "Accepted government-contract peer-leader risk using the old "
                    "full-basket peer-state definition."
                ),
                "exp-20260513-020": (
                    "Accepted IWM+peer-leader trend risk using the old full-basket "
                    "peer-state definition."
                ),
                "exp-20260513-025": (
                    "Rejected peer-leader breakout risk; this run changes only the "
                    "definition consumed by accepted peer-state helpers, not a new "
                    "breakout allocation slice."
                ),
                "exp-20260513-028": (
                    "Accepted single-event defense-only 1.05x; this run keeps that "
                    "scalar fixed as the before stack."
                ),
            },
            "3_single_causal_variable": (
                "Only space_peer_momentum_state_definition changes. Candidate pool, "
                "event seeds, all accepted Space scalars, trend targets, filters, "
                "ranking, add-ons, LLM/news replay, and live Space slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md canonical three fixed windows; require positive "
                "aggregate EV/PnL versus accepted exp-028, at least 2/3 improved EV "
                "windows, no EV-regressed window, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, >=50 total trades, and nonzero classification change."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_029_space_leave_one_out_peer_state.py"
            ),
        },
        "parameters": {
            "accepted_before_experiment": "exp-20260513-028",
            "accepted_single_event_defense_risk_scalar": (
                ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR
            ),
            "accepted_iwm_peer_leader_trend_risk_scalar": (
                ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR
            ),
            "before_peer_state_definition": (
                "own 20d momentum minus official Space basket average including own"
            ),
            "after_peer_state_definition": (
                "own 20d momentum minus equal-weight official Space peer average "
                "excluding own"
            ),
            "patched_experiment_modules": sorted(originals),
            "locked_variables": [
                "official Space candidate pool",
                "official Space event seeds",
                "base Space risk scalar",
                "accepted basket-positive scalar",
                "accepted perfect-TQS scalar",
                "accepted near-perfect trend-TQS scalar",
                "accepted peer-nonleader breakout scalar",
                "accepted IWM-relative small-cap leader scalar",
                "accepted IWM+peer-leader trend scalar",
                "accepted launch/lunar theme scalar",
                "accepted liquidity scalars",
                "accepted official customer-source scalars",
                "accepted financing/dilution profile scalar",
                "accepted multi-event catalyst-depth scalar",
                "accepted customer-source peer-leader scalar",
                "accepted government-contract peer-leader scalar",
                "accepted single-event defense scalar",
                "Space trend targets",
                "core signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use exp-20260510-028 augmented Space snapshots. "
            "The accepted_before variant reproduces exp-20260513-028 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. The tested peer-state definition "
                "uses production-visible basket momentum values, but any positive "
                "change must be promoted through shared default-off Space policy."
            ),
        },
        "gate2": {
            **gates,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "signal.space_basket_momentum_values",
                "signal.space_basket_momentum_values[ticker]",
                "signal.space_peer_momentum_state",
                "signal.space_peer_excess_momentum_20d_pct",
                "signal.space_iwm_relative_state",
                "sizing.shares_to_buy from shared sizing engine",
            ],
        },
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": False,
            "peer_state_definition_changed": True,
            "min_survival_rate_after": after["aggregate"]["min_survival_rate"],
            "passed": after["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "before_variant": before,
        "after_variant": after,
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": after["aggregate"],
            **{label: row["metrics"] for label, row in after["by_window"].items()},
        },
        "delta_metrics": {
            "aggregate": gate4["aggregate_delta_vs_before"],
            "by_window": gate4["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": gate4["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "gate_results": gate4,
        "gate4": gate4,
        "leave_one_out_diagnostics": diagnostics,
        "peer_dependent_adjustment_delta": peer_adjustment_delta,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space soft-ranking remains label-limited; this run uses deterministic "
                "production-visible price-derived peer-state metadata."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "promotion_required_if_accepted": False,
            "daily_report_metadata_changed": accepted,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": accepted,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not retry nearby peer-state definition variants on the "
            "same frozen snapshots. Next Space alpha should test a different "
            "production-visible catalyst/replacement-value boundary or improve "
            "official catalyst coverage quality without noisy ticker expansion."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_029_space_leave_one_out_peer_state.py",
            "data/experiments/exp-20260513-029/space_leave_one_out_peer_state.json",
            "docs/experiments/logs/exp-20260513-029.json",
            "docs/experiments/tickets/exp-20260513-029.json",
            "docs/experiments/artifacts/exp-20260513-029_space_leave_one_out_peer_state.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is label-limited; noisy ticker additions, mature satcom "
            "breadth, watch-liquidity peer/TQS/strategy scopes, broad defense-budget "
            "source scalars, primary-authority source scalars, customer-source "
            "peer-nonleader scaling, government-contract peer-nonleader scaling, "
            "peer-leader breakout risk, adjacent trend target width, and nearby "
            "single-event defense scalars were already rejected, accepted, or "
            "underpowered."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        payload,
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["delta_metrics"]["aggregate"][
                    "total_pnl_sum"
                ],
                "peer_state_changed_count": result["leave_one_out_diagnostics"][
                    "state_changed_count"
                ],
                "gate4_passed": result["gate4"]["passed"],
            },
            sort_keys=True,
        )
    )
