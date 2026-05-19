"""exp-20260513-109: clean SPY-leader non-confirmation risk allocation.

Tests one production-visible allocation variable on the accepted core stack:
already-qualified clean risk-on SPY-relative leaders keep their normal budget
only when the signal-day ticker return beats SPY. Non-confirmed leaders are
post-sizing de-risked in this scout.

This is not an entry filter, ranking change, exit change, universe change,
LLM/news change, or Space sleeve change.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260513-109"
EXPERIMENT_SLUG = "clean_spy_leader_nonconfirmation_risk"
MULTIPLIER_KEY = "clean_spy_leader_nonconfirmation_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [0.50, 0.75, 0.90]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _is_clean_spy_leader_nonconfirmation(sig: dict[str, Any]) -> bool:
    sizing = sig.get("sizing") or {}
    ticker_minus_spy = sig.get("ticker_minus_spy_signal_day_open_close_return_pct")
    return (
        sig.get("strategy") in {"trend_long", "breakout_long"}
        and sizing.get("spy_relative_leader_risk_on_multiplier_applied")
        == base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_RISK_MULTIPLIER
        and isinstance(ticker_minus_spy, (int, float))
        and sig.get("signal_day_ticker_outperformed_spy") is False
        and int(sizing.get("shares_to_buy") or 0) > 0
    )


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    new_shares = max(1, int(math.floor(shares * scalar)))
    if new_shares >= shares:
        return sizing

    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["clean_spy_leader_nonconfirmation_baseline_shares"] = shares
    out["clean_spy_leader_nonconfirmation_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value
        if portfolio_value
        else 0.0
    )
    out[MULTIPLIER_KEY] = scalar
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
            if _is_clean_spy_leader_nonconfirmation(sig):
                sizing = sig.get("sizing") or {}
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
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "spy_relative_leader": sig.get("spy_relative_leader"),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                            "ticker_minus_spy_signal_day_open_close_return_pct": (
                                sig.get(
                                    "ticker_minus_spy_signal_day_open_close_return_pct"
                                )
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


CURRENT_RISK_MULTIPLIER = 1.0


def _run_window(label: str, multiplier: float) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_size = base.portfolio_engine.size_signals
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    global CURRENT_RISK_MULTIPLIER
    CURRENT_RISK_MULTIPLIER = multiplier
    base.ADJUSTMENTS = []

    if multiplier != 1.0:
        base.portfolio_engine.size_signals = _make_size_wrapper(original_size)
        if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )

    try:
        engine = base.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        base.portfolio_engine.size_signals = original_size
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

    if result.get("error"):
        raise RuntimeError(f"{label} multiplier {multiplier} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "adjustments": list(base.ADJUSTMENTS),
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
    after_runs = {label: _run_window(label, multiplier) for label in base.WINDOWS}
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
        "adjustments": {label: after_runs[label]["adjustments"] for label in base.WINDOWS},
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
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
                adj=len(payload["adjustments"].get(label) or []),
            )
        )
    sweep_rows = [
        "| Multiplier | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_results"]:
        agg = row["delta_metrics"]["aggregate_delta"]
        sweep_rows.append(
            "| {mult:.2f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {dd:+.4f} | {adj} |".format(
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
            f"# {EXPERIMENT_ID} Clean SPY-Leader Non-Confirmation Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier for clean risk-on SPY-relative leaders whose signal-day ticker open-to-close return did not beat SPY.",
            "",
            *rows,
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "Production impact: no shared strategy code is promoted unless Gate 4 passes. A positive promotion would need the rule in shared `portfolio_engine.py`, with production continuing to call the same shared sizing path.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, 1.0) for label in base.WINDOWS}
    sweep_results = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(sweep_results)
    accepted = selected["passed"]
    decision = (
        "accepted_clean_spy_leader_nonconfirmation_risk"
        if accepted
        else "rejected_clean_spy_leader_nonconfirmation_risk"
    )
    interpretation = (
        "A clean SPY-relative leader non-confirmation haircut cleared Gate 4; promote only through shared sizing code and production parity tests."
        if accepted
        else "Clean SPY-relative leader non-confirmation de-risking did not clear the canonical three-window gate; keep the accepted clean-leader positive-confirmation top-up unchanged."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Clean risk-on SPY-relative leaders that fail to beat SPY on the signal day may be lower-quality continuation setups and should receive less capital."
        ),
        "change_type": "risk_allocation",
        "changed_variable": "clean_spy_leader_nonconfirmation_risk_multiplier",
        "single_causal_variable": (
            "post-sizing share multiplier for clean risk-on SPY-relative leaders whose signal-day ticker return did not outperform SPY"
        ),
        "parameters": {
            "selected_multiplier": selected["multiplier"],
            "sweep": RISK_MULTIPLIER_SWEEP,
            "requires_spy_relative_leader_risk_on_multiplier": (
                base.portfolio_engine.RISK_ON_SPY_RELATIVE_LEADER_RISK_MULTIPLIER
            ),
            "requires_signal_day_ticker_outperformed_spy": False,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "existing RS20/green/RS60/clean-leader positive-confirmation sizing",
                "portfolio heat and caps",
                "LLM/news replay",
                "Space sleeve",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core risk allocation: de-risk clean SPY-relative leaders when signal-day idiosyncratic confirmation is absent.",
            "2_history_check": {
                "exp-20260513-036": "Accepted positive-confirmation top-up for clean SPY-relative leaders; this tests the opposite non-confirmed cohort, not a nearby winner scalar.",
                "exp-20260513-038": "Rejected extra gap-cushion top-up for already-confirmed clean leaders; this does not add execution-cushion overlays.",
                "exp-20260513-027": "Rejected own-green slot priority; this does not change ranking or slot order.",
                "llm_soft_ranking": "Not used because current labeled forward set remains too thin for trustworthy LLM alpha.",
            },
            "3_single_causal_variable": "clean_spy_leader_nonconfirmation_risk_multiplier sweep only.",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed window, survival >= 5%, max drawdown drift <= 0.5 percentage points.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_109_clean_spy_leader_nonconfirmation_risk.py",
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
                "portfolio_engine spy_relative_leader_risk_on_multiplier_applied",
                "risk_engine ticker_minus_spy_signal_day_open_close_return_pct",
                "risk_engine signal_day_ticker_outperformed_spy",
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
        "adjustments": selected["adjustments"],
        "sizing_attribution": selected["sizing_attribution"],
        "expected_value_score_delta": selected["delta_metrics"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": selected["delta_metrics"]["aggregate_delta"][
            "total_pnl_sum"
        ],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "run_adapter_change_note": (
                "No production code changed in this scout; a positive result would be promoted through shared portfolio_engine sizing."
            ),
            "replay_only": False,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": None
        if accepted
        else "Use a different production-visible state variable or forward evidence; do not promote non-confirmation de-risking from this frozen-window scout.",
        "related_files": [
            "quant/experiments/exp_20260513_109_clean_spy_leader_nonconfirmation_risk.py",
            "data/experiments/exp-20260513-109/clean_spy_leader_nonconfirmation_risk.json",
            "experiments/logs/exp-20260513-109.json",
            "experiments/tickets/exp-20260513-109.json",
            "experiments/artifacts/exp-20260513-109_clean_spy_leader_nonconfirmation_risk.md",
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
        base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        base.REPO_ROOT
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
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
