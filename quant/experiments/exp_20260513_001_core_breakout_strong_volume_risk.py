"""exp-20260513-001: core breakout strong-volume risk allocation.

Alpha search. Tests one production-visible state variable on the accepted core
stack: already-qualified ``breakout_long`` signals whose existing
``conditions_met.volume_spike_ratio`` is greater than 2.0. The experiment
changes only a cap-aware post-sizing risk scalar for that state; it does not
change entry filters, ranking, exits, targets, universe membership, LLM/news
behavior, or portfolio heat.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260513-001"
EXPERIMENT_SLUG = "core_breakout_strong_volume_risk"
MULTIPLIER_KEY = "core_breakout_strong_volume_risk_multiplier_applied"
STRONG_VOLUME_RATIO = 2.0
RISK_MULTIPLIER_SWEEP = [0.75, 1.05, 1.10, 1.25, 1.50]

CURRENT_RISK_MULTIPLIER = 1.0


def _is_strong_volume_breakout(sig: dict[str, Any]) -> bool:
    volume_ratio = (sig.get("conditions_met") or {}).get("volume_spike_ratio")
    return (
        sig.get("strategy") == "breakout_long"
        and isinstance(volume_ratio, (int, float))
        and volume_ratio > STRONG_VOLUME_RATIO
    )


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            volume_ratio = (sig.get("conditions_met") or {}).get("volume_spike_ratio")
            sig["core_breakout_volume_spike_ratio"] = volume_ratio
            sig["core_breakout_strong_volume_state"] = _is_strong_volume_breakout(sig)
        return enriched

    return wrapped


def _scale_sizing(sizing: dict[str, Any], scalar: float, portfolio_value: float) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    if scalar <= 0:
        new_shares = 0
    elif scalar < 1.0:
        new_shares = max(1, int(math.floor(shares * scalar)))
    else:
        max_position_pct = float(sizing.get("max_position_pct_applied") or 0.40)
        cap_shares = max(1, int(math.floor(portfolio_value * max_position_pct / entry)))
        new_shares = min(
            max(shares, int(math.floor(shares * scalar))),
            cap_shares,
        )
    if new_shares == shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["core_breakout_strong_volume_baseline_shares"] = shares
    out["core_breakout_strong_volume_new_shares"] = new_shares
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
            if sig.get("core_breakout_strong_volume_state") and sizing.get("shares_to_buy"):
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
                            "volume_spike_ratio": sig.get("core_breakout_volume_spike_ratio"),
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

    original_enrich = base.risk_engine.enrich_signals
    original_size = base.portfolio_engine.size_signals
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    base.risk_engine.enrich_signals = _make_enrich_wrapper(original_enrich)
    base.portfolio_engine.size_signals = _make_size_wrapper(original_size)
    if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
        base.backtester_module.SIZING_MULTIPLIER_KEYS = (
            *base.backtester_module.SIZING_MULTIPLIER_KEYS,
            MULTIPLIER_KEY,
        )

    try:
        before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
        after_metrics: dict[str, dict[str, Any]] = {}
        adjustments: dict[str, list[dict[str, Any]]] = {}
        changed_trades: dict[str, dict[str, Any]] = {}
        sizing_attribution: dict[str, Any] = {}

        for label in base.WINDOWS:
            variant = base._run_window(label, variant=False)
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
    finally:
        base.risk_engine.enrich_signals = original_enrich
        base.portfolio_engine.size_signals = original_size
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

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
    max_drawdown_worse = (
        aggregate_after["max_drawdown_pct_max"]
        - aggregate_before["max_drawdown_pct_max"]
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and max_drawdown_worse <= 0.005
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
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "risk_multiplier": row["risk_multiplier"],
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
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
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
            f"# {EXPERIMENT_ID} Core Breakout Strong-Volume Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk scalar for existing `breakout_long` signals with `conditions_met.volume_spike_ratio > 2.0`. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
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
            "Production impact: replay-only scout unless Gate 4 passes and the rule is promoted into shared sizing policy with parity coverage.",
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
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_core_breakout_strong_volume_risk"
    )
    interpretation = (
        "Core strong-volume breakout risk allocation cleared the canonical gate and should be promoted through shared portfolio sizing policy before production use."
        if passed
        else "Core strong-volume breakout risk allocation did not clear the canonical three-window gate; do not promote this fixed volume-confirmation scalar on the frozen windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Breakout signals with volume_spike_ratio > 2.0 have stronger institutional confirmation than the minimum 1.5x breakout volume gate and may deserve a separate risk scalar."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "core_breakout_strong_volume_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk scalar for existing breakout_long signals with conditions_met.volume_spike_ratio > 2.0"
        ),
        "parameters": {
            "strong_volume_ratio": STRONG_VOLUME_RATIO,
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
            "1_alpha_hypothesis": "core state risk allocation using existing breakout volume-confirmation strength",
            "2_history_check": {
                "exp-20260508-026": "simple day-2 add-on volume confirmation rejected profitable add-ons, so this run targets entry sizing only.",
                "exp-20260512-020": "Space-only breakout strong-volume scalar failed on thin coverage; this run tests broader core breakout entries instead of Space retuning.",
                "exp-20260512-111/950": "momentum-acceleration top-ups regressed old_thin; this run uses an orthogonal signal-day volume-confirmation state.",
            },
            "3_single_causal_variable": "core_breakout_strong_volume_risk_multiplier with the threshold fixed at the already-existing 2.0x volume-spike boundary",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_001_core_breakout_strong_volume_risk.py",
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
                "signal_engine breakout_long conditions_met.volume_spike_ratio",
                "portfolio_engine sizing shares_to_buy",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
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
        else "Use forward breakout volume-bucket attribution or a different orthogonal entry-quality state before retrying.",
        "related_files": [
            "quant/experiments/exp_20260513_001_core_breakout_strong_volume_risk.py",
            "data/experiments/exp-20260513-001/core_breakout_strong_volume_risk.json",
            "docs/experiments/logs/exp-20260513-001.json",
            "docs/experiments/tickets/exp-20260513-001.json",
            "docs/experiments/artifacts/exp-20260513-001_core_breakout_strong_volume_risk.md",
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
    log_path = base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "selected_risk_multiplier": result["parameters"]["selected_risk_multiplier"],
            },
            indent=2,
            sort_keys=True,
        )
    )
