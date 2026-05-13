"""exp-20260512-111: core momentum-acceleration risk allocation.

Tests one production-visible state variable on the accepted core stack:
trend/breakout signals whose 10-day momentum is at least their 20-day momentum,
with both positive. This is a cap-aware post-sizing risk top-up scout, not an
entry filter or ranking change.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260512-111"
EXPERIMENT_SLUG = "core_momentum_acceleration_risk"
MULTIPLIER_KEY = "core_momentum_acceleration_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.05, 1.10, 1.15, 1.20]

CURRENT_RISK_MULTIPLIER = 1.0


def _make_compute_features_wrapper(original: Callable[..., dict[str, Any] | None]) -> Callable[..., dict[str, Any] | None]:
    return original


def _is_acceleration_state(mom10: Any, mom20: Any) -> bool:
    return (
        isinstance(mom10, (int, float))
        and isinstance(mom20, (int, float))
        and mom10 > 0
        and mom20 > 0
        and mom10 >= mom20
    )


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            features = features_dict.get(str(sig.get("ticker") or "")) or {}
            mom10 = features.get("momentum_10d_pct")
            mom20 = features.get("momentum_20d_pct")
            acceleration_state = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and _is_acceleration_state(mom10, mom20)
            )
            sig["momentum_10d_pct"] = mom10
            sig["momentum_20d_pct"] = mom20
            sig["momentum_acceleration_spread_pct"] = (
                round(mom10 - mom20, 6)
                if isinstance(mom10, (int, float)) and isinstance(mom20, (int, float))
                else None
            )
            sig["core_momentum_acceleration_state"] = acceleration_state
        return enriched

    return wrapped


def _scale_sizing(sizing: dict[str, Any], scalar: float, portfolio_value: float) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    max_position_pct = float(sizing.get("max_position_pct_applied") or 0.40)
    cap_shares = max(1, int(math.floor(portfolio_value * max_position_pct / entry)))
    desired_shares = max(shares, int(math.floor(shares * scalar)))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= shares:
        return sizing
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["core_momentum_acceleration_baseline_shares"] = shares
    out["core_momentum_acceleration_desired_shares"] = desired_shares
    out["core_momentum_acceleration_cap_shares"] = cap_shares
    out["core_momentum_acceleration_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get("core_momentum_acceleration_state") and sizing.get("shares_to_buy"):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "momentum_10d_pct": sig.get("momentum_10d_pct"),
                            "momentum_20d_pct": sig.get("momentum_20d_pct"),
                            "momentum_acceleration_spread_pct": sig.get(
                                "momentum_acceleration_spread_pct"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    global CURRENT_RISK_MULTIPLIER
    CURRENT_RISK_MULTIPLIER = multiplier

    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        variant = base._run_window(label, variant=True)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(before_runs[label]["trades"], variant["trades"])
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
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    ]
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
    )
    return {
        "risk_multiplier": multiplier,
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
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        rows.append(
            {
                "risk_multiplier": row["risk_multiplier"],
                "passed": row["passed"],
                "expected_value_score_delta": row["expected_value_score_delta"],
                "total_pnl_delta": row["total_pnl_delta"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            }
        )
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |",
        "|---:|:---:|---:|---:|---|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} |".format(
                mult=row["risk_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
            )
        )
    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |",
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
            f"# {EXPERIMENT_ID} Core Momentum Acceleration Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose 10-day momentum is at least 20-day momentum, with both positive. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. Positive promotion would require shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.",
        ]
    )


def run() -> dict[str, Any]:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown

    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: base._run_window(label, variant=False) for label in base.WINDOWS}
    candidates = [_candidate_payload(multiplier, before_runs) for multiplier in RISK_MULTIPLIER_SWEEP]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_core_momentum_acceleration_risk"
    )
    interpretation = (
        "Momentum-acceleration core risk top-up cleared the canonical three-window gate and requires shared policy implementation before production use."
        if passed
        else "Momentum-acceleration core risk top-up did not clear the canonical three-window gate; do not promote this state variable without a stronger discriminator."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Core trend/breakout signals with short-horizon momentum acceleration should deserve more capital because the newest half of the 20-day path is carrying the move."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "core_momentum_acceleration_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout signals where momentum_10d_pct >= momentum_20d_pct and both are positive"
        ),
        "parameters": {
            "state_definition": {
                "strategies": ["trend_long", "breakout_long"],
                "momentum_10d_pct": "> 0",
                "momentum_20d_pct": "> 0",
                "acceleration_condition": "momentum_10d_pct >= momentum_20d_pct",
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "pilot sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core state risk allocation using production-visible short-horizon momentum acceleration",
            "2_history_check": {
                "exp-20260512-106": "rejected adverse sector-tape haircut; not reused.",
                "exp-20260512-107": "rejected fixed positive sector-tape continuation top-up; not reused.",
                "exp-20260512-110": "accepted Space company-release source risk helper; this run stays in the core sleeve and avoids Space source retuning.",
                "llm_soft_ranking": "data remains thin, so this run avoids LLM soft-ranking.",
                "sec_semantics": "blocked by missing directional same-accession labels, so this run avoids SEC semantic expansion.",
            },
            "3_single_causal_variable": "core_momentum_acceleration_risk_multiplier with fixed production-visible acceleration state",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260512_111_core_momentum_acceleration_risk.py",
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
                "feature_layer momentum_10d_pct",
                "feature_layer momentum_20d_pct",
                "risk_engine enriched strategy",
                "portfolio_engine max_position_pct_applied",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": selected["delta_metrics"]["aggregate_delta"]["signals_generated_sum"],
            "signals_survived_delta": selected["delta_metrics"]["aggregate_delta"]["signals_survived_sum"],
            "minimum_after_survival_rate": selected["delta_metrics"]["aggregate_after"]["survival_rate_min"],
            "passed": selected["delta_metrics"]["aggregate_after"]["survival_rate_min"] >= 0.05,
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
        "llm_metrics": {"used_llm": False},
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
        else "Try a different production-visible core state variable, or require a stronger hold-quality discriminator before retesting acceleration.",
        "related_files": [
            "quant/experiments/exp_20260512_111_core_momentum_acceleration_risk.py",
            "data/experiments/exp-20260512-111/core_momentum_acceleration_risk.json",
            "docs/experiments/logs/exp-20260512-111.json",
            "docs/experiments/tickets/exp-20260512-111.json",
            "docs/experiments/artifacts/exp-20260512-111_core_momentum_acceleration_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


if __name__ == "__main__":
    result = run()
    base.persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_risk_multiplier": result["parameters"]["selected_risk_multiplier"],
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
