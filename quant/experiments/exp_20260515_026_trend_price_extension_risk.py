"""exp-20260515-026: trend-only price-extension risk allocation.

Tests one production-visible allocation state on the accepted core stack:
already-qualified ``trend_long`` non-ETF/non-commodity stock signals whose
``price_vs_200ma_extension_state`` is true.

The prior accepted price-vs-200MA extension top-up applied to both trend and
breakout signals. This experiment asks whether the slow-trend extension signal
has an additional trend-only allocation edge without changing entries, filters,
ranking, exits, targets, universe, LLM/news behavior, heat, slots, or the
already accepted broad extension top-up.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260515-026"
EXPERIMENT_SLUG = "trend_price_extension_risk"
MULTIPLIER_KEY = "trend_price_vs_200ma_extension_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.075, 1.10, 1.125, 1.15, 1.20]
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_RISK_MULTIPLIER = 1.0
ADJUSTMENTS: list[dict[str, Any]] = []


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl_by_experiment(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
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


def _trend_price_extension_state(sig: dict[str, Any]) -> bool:
    return (
        sig.get("strategy") == "trend_long"
        and sig.get("sector") not in EXCLUDED_SECTORS
        and sig.get("price_vs_200ma_extension_state") is True
    )


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
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
    out["trend_price_vs_200ma_extension_baseline_shares"] = shares
    out["trend_price_vs_200ma_extension_desired_shares"] = desired_shares
    out["trend_price_vs_200ma_extension_cap_shares"] = cap_shares
    out["trend_price_vs_200ma_extension_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
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
            sizing = sig.get("sizing") or {}
            if _trend_price_extension_state(sig) and sizing.get("shares_to_buy"):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "price_vs_200ma_pct": sig.get("price_vs_200ma_pct"),
                            "price_vs_200ma_extension_cutoff": sig.get(
                                "price_vs_200ma_extension_cutoff"
                            ),
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "max_position_pct_applied": sizing.get(
                                "max_position_pct_applied"
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
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, *, variant: bool) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_size = base.portfolio_engine.size_signals
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS
    trend_multiplier_attr = "TREND_PRICE_VS_200MA_EXTENSION_RISK_MULTIPLIER"
    original_trend_multiplier = getattr(
        base.portfolio_engine,
        trend_multiplier_attr,
        None,
    )

    global ADJUSTMENTS
    ADJUSTMENTS = []

    if original_trend_multiplier is not None:
        setattr(base.portfolio_engine, trend_multiplier_attr, 1.0)

    if variant:
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
        if original_trend_multiplier is not None:
            setattr(
                base.portfolio_engine,
                trend_multiplier_attr,
                original_trend_multiplier,
            )

    if result.get("error"):
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "adjustments": list(ADJUSTMENTS),
        "sizing_rule_signal_attribution": result.get(
            "sizing_rule_signal_attribution"
        )
        or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution")
        or {},
    }


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
        variant = _run_window(label, variant=True)
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
    adjusted_count = sum(len(rows) for rows in adjustments.values())
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
        and adjusted_count > 0
        and drawdown_guardrail_passed
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
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
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
            row["expected_value_score_delta"],
            row["total_pnl_delta"],
            -row["gate4"]["max_drawdown_worse"],
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
            "| {mult:.4f} | {gate} | {dev:+.4f} | ${dpnl:+,.2f} | {imp} | {reg} | {adj} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                gate="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                imp=", ".join(row["improved_windows"]) or "-",
                reg=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )

    result_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        result_rows.append(
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
            "# exp-20260515-026 Trend Price-vs-200MA Extension Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware extra post-sizing top-up for already-qualified `trend_long` non-ETF/non-commodity stocks with `price_vs_200ma_extension_state=true`. No entry filter, ranking, exit, target, universe, LLM, news, heat, slot, or broad extension-state definition changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *result_rows,
            "",
            "Production impact: promoted into shared `portfolio_engine.py`, `backtester.py` attribution keys, `docs/production_backtest_parity.md`, and focused parity tests. The experiment runner explicitly disables the promoted constant while replaying its own baseline and variant wrapper.",
            "",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, variant=False) for label in base.WINDOWS}
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_trend_price_extension_risk"
    )
    interpretation = (
        "Trend-only price-vs-200MA extension cleared the canonical three-window gate and should be promoted only through shared production/backtest sizing policy."
        if passed
        else "Trend-only price-vs-200MA extension did not clear the canonical three-window gate."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted price-vs-200MA extension state is fundamentally a slow-trend quality field. "
            "Inside the already-qualified core candidate set, trend_long extension signals may deserve "
            "an additional small cap-aware allocation top-up, while breakout_long extension exposure "
            "should remain on the existing broad 1.025x helper."
        ),
        "change_type": "risk_allocation",
        "changed_variable": "trend_price_vs_200ma_extension_risk_multiplier",
        "single_causal_variable": (
            "extra cap-aware post-sizing risk top-up for trend_long non-ETF/non-commodity stock signals "
            "with price_vs_200ma_extension_state=true"
        ),
        "parameters": {
            "state_definition": {
                "strategy": "trend_long",
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "requires_price_vs_200ma_extension_state": True,
                "keeps_existing_broad_price_extension_topup": True,
            },
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "existing broad price-vs-200MA extension top-up",
                "all other sizing multipliers",
                "portfolio heat",
                "MAX_POSITIONS",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260515-018": "Accepted broad trend/breakout price-vs-200MA extension at 1.025x; larger broad scalars regressed late_strong or drawdown.",
                "exp-20260515-020": "Rejected RS60 x price-vs-200MA extension overlap top-up because late_strong regressed.",
                "exp-20260515-024_price_extension_nonconfirmation_haircut": "Rejected haircutting extension signals lacking signal-day SPY outperformance.",
            },
            "why_this_branch": (
                "Strategy type is a separate production-visible discriminator from the exhausted RS60/confirmation overlaps; "
                "this keeps breakout extension unchanged instead of retrying the broad extension scalar."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: trend_long price-vs-200MA extension may identify stronger slow-trend leaders among already-qualified core signals."
            ),
            "2_history_check": (
                "Broad price extension was accepted only at 1.025x; RS60 overlap and nonconfirmation variants failed. No trend-only extension allocation scout was found."
            ),
            "3_single_causal_variable": "trend_price_vs_200ma_extension_risk_multiplier only",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, nonzero adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_026_trend_price_extension_risk.py"
            ),
        },
        "gate1": {
            "baseline_source": "rerun inside this script using docs/backtesting.md canonical fixed-snapshot three-window replay",
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "risk_engine price_vs_200ma_extension_state",
                "risk_engine sector",
                "portfolio_engine strategy",
                "portfolio_engine max_position_pct_applied",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
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
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "notes": (
                "Promoted through shared portfolio_engine.size_signals; run.py and backtester.py both use the shared sizing policy. "
                "backtester.py only adds attribution for the applied multiplier."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "Do not retry trend-only price extension on frozen windows without forward attribution or a different production-visible discriminator."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_026_trend_price_extension_risk.py",
            "data/experiments/exp-20260515-026/trend_price_extension_risk.json",
            "docs/experiments/logs/exp-20260515-026_trend_price_extension_risk.json",
            "docs/experiments/tickets/exp-20260515-026_trend_price_extension_risk.json",
            "docs/experiments/artifacts/exp-20260515-026_trend_price_extension_risk.md",
            "docs/experiment_log.jsonl",
            "quant/constants.py",
            "quant/portfolio_engine.py",
            "quant/backtester.py",
            "quant/test_production_parity.py",
            "docs/backtesting.md",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
            "docs/production_backtest_parity.md",
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def main() -> None:
    payload = run()
    out_dir = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    docs_dir = base.REPO_ROOT / "docs" / "experiments"
    _write_json(out_dir / f"{EXPERIMENT_SLUG}.json", payload)
    _write_json(
        docs_dir / "logs" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.json",
        payload,
    )
    _write_json(
        docs_dir / "tickets" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Trend price-vs-200MA extension risk",
            "decision": payload["decision"],
            "summary": (
                f"Selected {payload['parameters']['selected_risk_multiplier']}x; "
                f"Gate4={payload['gate4']['passed']}; "
                f"dEV={payload['expected_value_score_delta']:+.4f}; "
                f"dPnL=${payload['total_pnl_delta']:+,.2f}"
            ),
        },
    )
    artifact_path = (
        docs_dir / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(payload["artifact_markdown"], encoding="utf-8")
    _upsert_jsonl_by_experiment(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "selected": payload["parameters"]["selected_risk_multiplier"],
                "gate4": payload["gate4"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
