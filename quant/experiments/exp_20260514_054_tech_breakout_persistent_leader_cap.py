"""exp-20260514-054: Technology breakout persistent-leader cap scout.

Tests one production-visible allocation variable on the accepted core stack:
already-qualified Technology breakout signals that are both RS60 persistent
leaders and clean-SPY signal-day leaders may be capped too tightly by the
generic clean-SPY max-position cap. This is a shadow scout; it does not change
entries, exits, ranking, universe, LLM/news, Space sleeves, heat, or slots.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-054"
EXPERIMENT_SLUG = "tech_breakout_persistent_leader_cap"
STATE_KEY = "tech_breakout_persistent_clean_spy_leader_state"
CAP_KEY = "tech_breakout_persistent_leader_max_position_pct_applied"
CAP_SWEEP = [0.55, 0.575, 0.60]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_MAX_POSITION_PCT = 0.55

PRE_SIZING_MULTIPLIER_KEYS = (
    "tqs_risk_multiplier_applied",
    "risk_on_unmodified_risk_multiplier_applied",
    "spy_relative_leader_risk_on_multiplier_applied",
    "rs20_entry_state_risk_multiplier_applied",
    "signal_day_ticker_green_risk_multiplier_applied",
    "rs60_top_quintile_risk_multiplier_applied",
    "clean_spy_leader_signal_day_risk_multiplier_applied",
    "breakout_tech_dte_risk_multiplier_applied",
)


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    def wrapped(
        ticker: str,
        ohlcv_data: Any,
        earnings_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return original(ticker, ohlcv_data, earnings_data)

    return wrapped


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            sig[STATE_KEY] = bool(
                sig.get("strategy") == "breakout_long"
                and sig.get("sector") == "Technology"
                and sig.get("rs60_top_quintile_state") is True
                and sig.get("signal_day_ticker_outperformed_spy") is True
            )
        return enriched

    return wrapped


def _pre_sizing_risk_pct(sizing: dict[str, Any]) -> float | None:
    risk_pct = sizing.get("base_risk_pct")
    if not isinstance(risk_pct, (int, float)):
        return None
    out = float(risk_pct)
    for key in PRE_SIZING_MULTIPLIER_KEYS:
        value = sizing.get(key)
        if isinstance(value, (int, float)):
            out *= float(value)
    return out


def _resize_with_cap(
    sizing: dict[str, Any],
    portfolio_value: float,
) -> dict[str, Any]:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    risk_pct = _pre_sizing_risk_pct(sizing)
    if old_shares <= 0 or entry <= 0 or net_risk_per_share <= 0 or risk_pct is None:
        return sizing

    old_cap_pct = float(sizing.get("max_position_pct_applied") or 0.40)
    raw_shares = max(
        1,
        int(math.floor((portfolio_value * risk_pct) / net_risk_per_share)),
    )
    old_cap_shares = max(1, int(math.floor(portfolio_value * old_cap_pct / entry)))
    new_cap_shares = max(
        1,
        int(math.floor(portfolio_value * CURRENT_MAX_POSITION_PCT / entry)),
    )
    new_shares = min(raw_shares, new_cap_shares)
    if new_shares <= old_shares:
        return sizing

    out = dict(sizing)
    out["tech_breakout_persistent_leader_baseline_shares"] = old_shares
    out["tech_breakout_persistent_leader_raw_shares"] = raw_shares
    out["tech_breakout_persistent_leader_old_cap_shares"] = old_cap_shares
    out["tech_breakout_persistent_leader_new_cap_shares"] = new_cap_shares
    out["tech_breakout_persistent_leader_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    )
    out["max_position_pct_applied"] = CURRENT_MAX_POSITION_PCT
    out[CAP_KEY] = CURRENT_MAX_POSITION_PCT
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
            clean_spy_mult = sizing.get(
                "clean_spy_leader_signal_day_risk_multiplier_applied"
            )
            if (
                sig.get(STATE_KEY)
                and isinstance(clean_spy_mult, (int, float))
                and clean_spy_mult > 1.0
                and sizing.get("shares_to_buy")
            ):
                adjusted_sizing = _resize_with_cap(sizing, portfolio_value)
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "max_position_pct": CURRENT_MAX_POSITION_PCT,
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "raw_shares": adjusted_sizing.get(
                                "tech_breakout_persistent_leader_raw_shares"
                            ),
                            "old_cap_shares": adjusted_sizing.get(
                                "tech_breakout_persistent_leader_old_cap_shares"
                            ),
                            "new_cap_shares": adjusted_sizing.get(
                                "tech_breakout_persistent_leader_new_cap_shares"
                            ),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
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
                            "clean_spy_leader_multiplier": clean_spy_mult,
                            "breakout_tech_dte_risk_multiplier": sizing.get(
                                "breakout_tech_dte_risk_multiplier_applied"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _wire_shadow_policy() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = CAP_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper


def _run_window(label: str, cap: float | None) -> dict[str, Any]:
    global CURRENT_MAX_POSITION_PCT
    previous_cap = CURRENT_MAX_POSITION_PCT
    if cap is not None:
        CURRENT_MAX_POSITION_PCT = cap
    try:
        return base._run_window(label, variant=cap is not None)
    finally:
        CURRENT_MAX_POSITION_PCT = previous_cap


def _candidate_payload(
    cap: float,
    before_runs: dict[str, dict[str, Any]],
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_runs = {label: _run_window(label, cap) for label in base.WINDOWS}
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
    adjusted_count = sum(len(after_runs[label]["adjustments"]) for label in base.WINDOWS)
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
        and drawdown_guardrail_passed
    )
    return {
        "max_position_pct": cap,
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
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "adjustments": {
            label: after_runs[label]["adjustments"] for label in base.WINDOWS
        }
        if include_details
        else None,
        "changed_trades": {
            label: base._changed_trades(
                before_runs[label]["trades"],
                after_runs[label]["trades"],
            )
            for label in base.WINDOWS
        }
        if include_details
        else None,
        "sizing_attribution": {
            label: {
                "signal": after_runs[label]["sizing_rule_signal_attribution"].get(
                    CAP_KEY
                ),
                "trade": after_runs[label]["sizing_rule_trade_attribution"].get(
                    CAP_KEY
                ),
            }
            for label in base.WINDOWS
        }
        if include_details
        else None,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    rows = passed or candidates
    return max(
        rows,
        key=lambda row: (
            1 if row["passed"] else 0,
            row["delta_metrics"]["aggregate_delta"]["expected_value_score_sum"],
            row["delta_metrics"]["aggregate_delta"]["total_pnl_sum"],
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "max_position_pct": row["max_position_pct"],
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
            f"# {EXPERIMENT_ID} Technology Breakout Persistent-Leader Cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: max position cap for already-qualified `breakout_long` Technology signals with `rs60_top_quintile_state=true`, `signal_day_ticker_outperformed_spy=true`, and active clean-SPY leader sizing. Entries, exits, ranking, universe, LLM/news logic, heat, and slots were unchanged.",
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
            "Production impact: shadow scout only. Positive promotion would require shared `portfolio_engine` cap policy plus attribution/parity tests before live/default behavior changes.",
        ]
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: base.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: base.Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
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
    _wire_shadow_policy()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, None) for label in base.WINDOWS}
    sweep_results = [_candidate_payload(cap, before_runs) for cap in CAP_SWEEP]
    selected_summary = _select_candidate(sweep_results)
    selected = _candidate_payload(
        selected_summary["max_position_pct"],
        before_runs,
        include_details=True,
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_tech_breakout_persistent_leader_cap"
    )
    interpretation = (
        "Technology breakout persistent leaders were cap-bound and the selected cap improved the canonical three-window stack without EV regression."
        if selected["passed"]
        else "The persistent Technology breakout cap only affected too little of the fixed-snapshot sample or failed the three-window gate; do not promote without new forward evidence."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Within the accepted clean-SPY leader allocation stack, Technology breakout signals that also have RS60 persistence may deserve more cap room than the generic clean-SPY max-position cap."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "max_position_pct_for_technology_breakout_persistent_clean_spy_leaders",
        "single_causal_variable": (
            "max_position_pct for already-qualified Technology breakout signals with RS60 top-quintile state and active clean-SPY leader sizing"
        ),
        "parameters": {
            "cap_sweep": CAP_SWEEP,
            "selected_max_position_pct": selected["max_position_pct"],
            "target_sleeve": {
                "strategy": "breakout_long",
                "sector": "Technology",
                "rs60_top_quintile_state": True,
                "signal_day_ticker_outperformed_spy": True,
                "clean_spy_leader_signal_day_risk_multiplier_applied": "> 1.0",
            },
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "raw Technology breakout DTE multiplier",
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
                "exp-20260514-019": (
                    "Rejected generic RS60 top-quintile cap expansion; this run tests the narrower Technology breakout plus clean-SPY leader interaction."
                ),
                "exp-20260514-045": (
                    "Rejected triple-momentum clean-SPY cap expansion because only late_strong improved; this run isolates the Technology breakout RS60 subset."
                ),
                "exp-20260514-046": (
                    "Rejected fresh RS20 non-RS60 risk top-up because old_thin regressed and DD worsened; this run tests persistent rather than fresh leadership."
                ),
                "exp-20260514-050": (
                    "Accepted clean-SPY leader cap/risk allocation; this run asks whether a narrower persistent Technology breakout pocket is still cap-bound."
                ),
            },
            "why_not_llm_or_space": (
                "LLM soft-ranking and more Space semantic refinements are currently sample/attribution constrained. This run uses deterministic fields already visible to production sizing."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: persistent Technology breakout clean-SPY leaders may need more cap room."
            ),
            "2_history_check": (
                "Generic RS60 caps and triple-momentum caps were rejected; this narrows the variable to Technology breakout signals with active clean-SPY sizing."
            ),
            "3_single_causal_variable": (
                "target-sleeve max_position_pct only"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, nonzero adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_054_tech_breakout_persistent_leader_cap.py"
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
                "risk_engine rs60_top_quintile_state",
                "risk_engine signal_day_ticker_outperformed_spy",
                "portfolio_engine strategy",
                "portfolio_engine sector",
                "portfolio_engine clean_spy_leader_signal_day_risk_multiplier_applied",
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
            "survival_rate_min_after": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ],
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
        "sweep_summary": _sweep_summary(sweep_results),
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "positive_promotion_requirement": (
                "If accepted later, implement through shared portfolio sizing policy and add focused production/backtest attribution parity before default use."
            ),
        },
        "why_not_other_changes": (
            "Avoided LLM/Space sample-limited work, broad filters, candidate-pool noise, and nearby all-sector RS60 or triple-momentum cap retunes."
        ),
        "known_risks": [
            "Narrow cap-room allocation can be sample-thin.",
            "This shadow policy is not production behavior unless promoted into shared sizing code.",
            "Cap expansion can increase tail loss if the sleeve later admits weaker Technology breakouts.",
        ],
        "decision_reason": interpretation,
        "rejection_reason": None
        if selected["passed"]
        else interpretation,
        "next_evidence_needed": (
            "New forward closed Technology breakout leader trades or an independent pre-entry discriminator that improves at least two canonical windows without EV regression."
        ),
    }

    data_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    artifact_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    _write_json(data_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, payload)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(_safe(result), indent=2, ensure_ascii=True, sort_keys=True))
