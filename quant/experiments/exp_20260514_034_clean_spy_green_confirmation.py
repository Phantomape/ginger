"""exp-20260514-034: clean SPY-leader green confirmation scout.

Tests one production-visible allocation variable on the accepted core stack:
the already-accepted clean SPY-relative signal-day top-up/cap should require
the ticker to be absolutely green on its own signal day, not only less-red than
SPY.

This is a shadow experiment only unless Gate 4 passes. It does not change
entries, filters, ranking, exits, target widths, universe, LLM/news logic,
Space sleeves, heat, or slot limits.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-034"
EXPERIMENT_SLUG = "clean_spy_green_confirmation"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
CLEAN_RISK_KEY = "clean_spy_leader_signal_day_risk_multiplier_applied"
CLEAN_CAP_KEY = "clean_spy_leader_signal_day_max_position_pct_applied"


def _upsert_jsonl(path: base.Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
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


def _candidate_for_green_confirmation(sig: dict[str, Any]) -> bool:
    return (
        sig.get("signal_day_ticker_outperformed_spy") is True
        and sig.get("strategy") in {"trend_long", "breakout_long"}
        and sig.get("regime_exit_bucket") == "risk_on"
        and sig.get("spy_relative_leader") is True
    )


def _clean_rule_applied(sizing: dict[str, Any]) -> bool:
    return (
        float(sizing.get(CLEAN_RISK_KEY) or 1.0) > 1.0
        or sizing.get(CLEAN_CAP_KEY) is not None
    )


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        adjusted_signals = []
        missing_green_field = 0
        for sig in signals:
            if _candidate_for_green_confirmation(sig) and (
                "signal_day_ticker_green_candle" not in sig
            ):
                missing_green_field += 1

            if (
                _candidate_for_green_confirmation(sig)
                and sig.get("signal_day_ticker_green_candle") is not True
            ):
                adjusted = dict(sig)
                adjusted["clean_spy_green_confirmation_removed"] = True
                adjusted["signal_day_ticker_outperformed_spy"] = False
                adjusted_signals.append(adjusted)
            else:
                adjusted_signals.append(sig)

        baseline_sized = original(signals, portfolio_value, risk_pct=risk_pct)
        variant_sized = original(adjusted_signals, portfolio_value, risk_pct=risk_pct)

        for before_sig, after_sig in zip(baseline_sized, variant_sized):
            before_sizing = before_sig.get("sizing") or {}
            after_sizing = after_sig.get("sizing") or {}
            if not _clean_rule_applied(before_sizing):
                continue
            if before_sig.get("signal_day_ticker_green_candle") is True:
                continue
            before_shares = int(before_sizing.get("shares_to_buy") or 0)
            after_shares = int(after_sizing.get("shares_to_buy") or 0)
            if before_shares == after_shares and _clean_rule_applied(after_sizing):
                continue
            base.ADJUSTMENTS.append(
                {
                    "ticker": before_sig.get("ticker"),
                    "strategy": before_sig.get("strategy"),
                    "sector": before_sig.get("sector"),
                    "entry_price": before_sig.get("entry_price"),
                    "trade_quality_score": before_sig.get("trade_quality_score"),
                    "regime_exit_bucket": before_sig.get("regime_exit_bucket"),
                    "regime_exit_score": before_sig.get("regime_exit_score"),
                    "signal_day_ticker_green_candle": before_sig.get(
                        "signal_day_ticker_green_candle"
                    ),
                    "signal_day_ticker_outperformed_spy": before_sig.get(
                        "signal_day_ticker_outperformed_spy"
                    ),
                    "ticker_minus_spy_signal_day_open_close_return_pct": (
                        before_sig.get(
                            "ticker_minus_spy_signal_day_open_close_return_pct"
                        )
                    ),
                    "baseline_shares": before_shares,
                    "variant_shares": after_shares,
                    "baseline_clean_risk_multiplier": before_sizing.get(
                        CLEAN_RISK_KEY
                    ),
                    "variant_clean_risk_multiplier": after_sizing.get(CLEAN_RISK_KEY),
                    "baseline_clean_cap": before_sizing.get(CLEAN_CAP_KEY),
                    "variant_clean_cap": after_sizing.get(CLEAN_CAP_KEY),
                    "missing_green_field_in_batch": missing_green_field,
                }
            )
        return variant_sized

    return wrapped


def _run_window(label: str, require_green: bool) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_size = base.portfolio_engine.size_signals
    base.ADJUSTMENTS = []

    if require_green:
        base.portfolio_engine.size_signals = _make_size_wrapper(original_size)

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

    if result.get("error"):
        kind = "require_green" if require_green else "baseline"
        raise RuntimeError(f"{label} {kind} failed: {result['error']}")
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


def _changed_trade_count(changed: dict[str, Any]) -> int:
    return int(changed.get("added_count") or 0) + int(
        changed.get("removed_count") or 0
    ) + int(changed.get("common_pnl_changed_count") or 0)


def _candidate_payload(
    before_runs: dict[str, dict[str, Any]],
    after_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
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
    changed_trades = {
        label: base._changed_trades(
            before_runs[label]["trades"],
            after_runs[label]["trades"],
        )
        for label in base.WINDOWS
    }
    adjusted_signal_count = sum(
        len(after_runs[label]["adjustments"]) for label in base.WINDOWS
    )
    adjusted_trade_count = sum(
        _changed_trade_count(changed_trades[label]) for label in base.WINDOWS
    )
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = (
        max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    field_audit = {
        "missing_green_field_count": sum(
            int(row.get("missing_green_field_in_batch") or 0)
            for label in base.WINDOWS
            for row in after_runs[label]["adjustments"]
        ),
        "clean_non_green_adjustments": adjusted_signal_count,
    }
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_signal_count > 0
        and adjusted_trade_count > 0
        and field_audit["missing_green_field_count"] == 0
        and drawdown_guardrail_passed
    )
    return {
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
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "field_audit": field_audit,
        "adjustments": {
            label: after_runs[label]["adjustments"] for label in base.WINDOWS
        },
        "changed_trades": changed_trades,
        "sizing_attribution": {
            label: {
                "before_signal": before_runs[label][
                    "sizing_rule_signal_attribution"
                ].get(CLEAN_RISK_KEY),
                "after_signal": after_runs[label][
                    "sizing_rule_signal_attribution"
                ].get(CLEAN_RISK_KEY),
                "before_trade": before_runs[label][
                    "sizing_rule_trade_attribution"
                ].get(CLEAN_RISK_KEY),
                "after_trade": after_runs[label][
                    "sizing_rule_trade_attribution"
                ].get(CLEAN_RISK_KEY),
            }
            for label in base.WINDOWS
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


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
                adj=len(payload["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Clean SPY Green Confirmation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: require `signal_day_ticker_green_candle=True` before the accepted clean SPY-relative signal-day top-up/cap can apply. No entries, ranking, exits, universe, LLM/news, heat, slots, or other sizing rules changed.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            f"- Passed: `{payload['gate4']['passed']}`",
            f"- Aggregate dEV: `{payload['expected_value_score_delta']:+.4f}`",
            f"- Aggregate dPnL: `${payload['total_pnl_delta']:+,.2f}`",
            f"- Improved windows: `{payload['gate4']['improved_windows']}`",
            f"- Regressed windows: `{payload['gate4']['regressed_windows']}`",
            f"- Adjusted signal count: `{payload['gate4']['adjusted_signal_count']}`",
            f"- Adjusted trade count: `{payload['gate4']['adjusted_trade_count']}`",
            "",
            "Production impact: shadow scout only unless promoted into shared `portfolio_engine.py`; the shared policy is called by both `backtester.py` and `run.py`.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, False) for label in base.WINDOWS}
    after_runs = {label: _run_window(label, True) for label in base.WINDOWS}
    selected = _candidate_payload(before_runs, after_runs)
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_clean_spy_green_confirmation"
    )
    interpretation = (
        "Clean SPY-relative signal-day allocation improved when absolute own-green confirmation was required; promote only in shared portfolio policy."
        if selected["passed"]
        else "Requiring absolute own-green confirmation for clean SPY-relative signal-day allocation did not beat the accepted core stack across the canonical three-window gate."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Signals that beat SPY only because SPY was weaker may be lower-quality "
            "follow-through states. Requiring the ticker itself to be green before "
            "the accepted clean SPY-relative signal-day top-up/cap applies may "
            "avoid weak relative-only exposure without changing entries."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": (
            "clean_spy_leader_signal_day_topup_and_cap_requires_own_green_candle"
        ),
        "single_causal_variable": (
            "eligibility condition for the existing clean SPY-relative signal-day "
            "risk/cap allocation"
        ),
        "parameters": {
            "required_signal_day_ticker_green_candle": True,
            "existing_clean_risk_multiplier": (
                base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER
            ),
            "existing_clean_max_position_pct": (
                base.portfolio_engine.CLEAN_SPY_LEADER_SIGNAL_DAY_MAX_POSITION_PCT
            ),
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all other sizing multipliers",
                "portfolio heat",
                "MAX_POSITIONS",
                "LLM/news replay",
                "Space sleeve",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: narrow the accepted clean SPY-relative "
                "top-up/cap to absolute own-green signal days."
            ),
            "2_history_check": {
                "exp-20260513-036": (
                    "accepted clean SPY-relative signal-day risk allocation; this "
                    "tests a qualifier on that accepted allocation, not a scalar retune."
                ),
                "exp-20260514-032": (
                    "rejected signal-day own-green top-up requiring SPY outperformance; "
                    "this tests the inverse relation on the clean SPY-relative path."
                ),
                "exp-20260514-028": (
                    "tested strong-close replacement for the generic green top-up; "
                    "this does not replace the generic green top-up."
                ),
                "llm_soft_ranking": (
                    "Skipped because production-aligned LLM soft-ranking records remain "
                    "too sparse for credible alpha validation."
                ),
            },
            "3_single_causal_variable": (
                "clean SPY-relative signal-day allocation eligibility requires own-green candle"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, "
                "survival >= 5%, adjusted trades > 0, no missing green field, "
                "max drawdown drift <= 0.5 percentage points."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_034_clean_spy_green_confirmation.py"
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
                "risk_engine signal_day_ticker_green_candle",
                "risk_engine signal_day_ticker_outperformed_spy",
                "risk_engine spy_relative_leader",
                "portfolio_engine clean_spy_leader_signal_day sizing fields",
            ],
            "field_audit": selected["field_audit"],
            "passed": (
                gate2["passed"]
                and selected["field_audit"]["missing_green_field_count"] == 0
            ),
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
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains production-aligned sample limited; this "
                "deterministic allocation test is replayable on fixed OHLCV snapshots."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the green qualifier inside shared "
                "portfolio_engine.py so both backtester.py and run.py use the same policy."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": None
        if selected["passed"]
        else (
            "Do not add an own-green qualifier to clean SPY-relative allocation "
            "without materially different evidence; move to another deterministic "
            "allocation alpha."
        ),
        "related_files": [
            "quant/experiments/exp_20260514_034_clean_spy_green_confirmation.py",
            "data/experiments/exp-20260514-034/clean_spy_green_confirmation.json",
            "docs/experiments/logs/exp-20260514-034.json",
            "docs/experiments/tickets/exp-20260514-034.json",
            "docs/experiments/artifacts/exp-20260514-034_clean_spy_green_confirmation.md",
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
    ticket_path = (
        base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


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
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "adjusted_trade_count": result["gate4"]["adjusted_trade_count"],
                "field_audit": result["gate2"]["field_audit"],
            },
            indent=2,
            sort_keys=True,
        )
    )
