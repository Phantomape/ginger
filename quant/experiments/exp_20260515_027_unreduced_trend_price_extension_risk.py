"""exp-20260515-027: unreduced trend price-extension risk allocation.

Tests one production-visible refinement to the accepted
``trend_price_vs_200ma_extension_risk_multiplier`` from exp-20260515-026:
keep the accepted 1.125x trend-only extension top-up only when the signal has
not already received an explicit risk haircut from existing shared sizing
policy. This asks whether the extension top-up should avoid partially undoing
older de-risking rules, without changing entries, exits, targets, ranking,
candidate pool, LLM/news behavior, heat, slots, or the broad price-extension
top-up.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260515-027"
EXPERIMENT_SLUG = "unreduced_trend_price_extension_risk"
MULTIPLIER_KEY = "trend_price_vs_200ma_extension_risk_multiplier_applied"
ACCEPTED_TREND_EXTENSION_MULTIPLIER = 1.125
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

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


def _prior_haircut_keys(sizing: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key, value in sizing.items():
        if not key.endswith("_risk_multiplier_applied"):
            continue
        if key in {
            "price_vs_200ma_extension_risk_multiplier_applied",
            "trend_price_vs_200ma_extension_risk_multiplier_applied",
        }:
            continue
        if isinstance(value, (int, float)) and value < 1.0:
            keys.append(key)
    return sorted(keys)


def _scale_sizing(
    sizing: dict[str, Any],
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
    desired_shares = max(
        shares,
        int(math.floor(shares * ACCEPTED_TREND_EXTENSION_MULTIPLIER)),
    )
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
    out[MULTIPLIER_KEY] = ACCEPTED_TREND_EXTENSION_MULTIPLIER
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
        out: list[dict[str, Any]] = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            haircut_keys = _prior_haircut_keys(sizing)
            if (
                _trend_price_extension_state(sig)
                and not haircut_keys
                and sizing.get("shares_to_buy")
            ):
                adjusted_sizing = _scale_sizing(sizing, portfolio_value)
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
                            "skipped_prior_haircut_keys": haircut_keys,
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, *, restricted_variant: bool) -> dict[str, Any]:
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

    if restricted_variant:
        if original_trend_multiplier is not None:
            setattr(base.portfolio_engine, trend_multiplier_attr, 1.0)
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
        mode = "restricted" if restricted_variant else "baseline"
        raise RuntimeError(f"{label} {mode} failed: {result['error']}")
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


def _gate4(delta_metrics: dict[str, Any], adjustments: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_window = delta_metrics["by_window"]
    improved = [
        label
        for label, delta in by_window.items()
        if (delta.get("expected_value_score") or 0.0) > 0
    ]
    regressed = [
        label
        for label, delta in by_window.items()
        if (delta.get("expected_value_score") or 0.0) < 0
    ]
    aggregate_delta = delta_metrics["aggregate_delta"]
    max_drawdown_worse = aggregate_delta["max_drawdown_pct_max"]
    adjusted_signal_count = sum(len(rows) for rows in adjustments.values())
    passed = (
        (aggregate_delta["expected_value_score_sum"] or 0.0) > 0
        and (aggregate_delta["total_pnl_sum"] or 0.0) > 0
        and len(improved) >= 2
        and not regressed
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and delta_metrics["aggregate_after"]["survival_rate_min"] >= 0.05
        and delta_metrics["aggregate_after"]["trade_count_sum"] >= 50
        and adjusted_signal_count > 0
    )
    return {
        "passed": passed,
        "improved_windows": improved,
        "regressed_windows": regressed,
        "max_drawdown_worse": max_drawdown_worse,
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
        "adjusted_signal_count": adjusted_signal_count,
        "drawdown_guardrail_passed": max_drawdown_worse
        <= MAX_DRAWDOWN_WORSE_GUARDRAIL,
    }


def _delta_metrics(
    before_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "by_window": {
            label: base._delta(after_metrics[label], before_metrics[label])
            for label in base.WINDOWS
        },
        "aggregate_before": base._aggregate(before_metrics),
        "aggregate_after": base._aggregate(after_metrics),
        "aggregate_delta": base._aggregate_delta(
            base._aggregate(after_metrics),
            base._aggregate(before_metrics),
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260515-027 Unreduced Trend Price Extension Risk",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: restrict the accepted 1.125x trend-only "
            "price-vs-200MA extension top-up to signals with no pre-existing "
            "risk-haircut multiplier. Entries, exits, ranking, universe, LLM/news, "
            "heat, slots, broad price-extension top-up, and the accepted scalar "
            "were unchanged."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bp:,.2f} | ${ap:,.2f} | ${dp:+,.2f} | {ddd:+.4f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bp=before["total_pnl"],
                ap=after["total_pnl"],
                dp=delta["total_pnl"],
                ddd=delta["max_drawdown_pct"],
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    lines.extend(
        [
            "",
            "Production impact: shadow scout only unless promoted into shared `portfolio_engine.py`, backtest attribution, and focused parity tests.",
        ]
    )
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: _run_window(label, restricted_variant=False) for label in base.WINDOWS
    }
    after_runs = {
        label: _run_window(label, restricted_variant=True) for label in base.WINDOWS
    }
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in base.WINDOWS}
    adjustments = {label: after_runs[label]["adjustments"] for label in base.WINDOWS}
    changed_trades = {
        label: base._changed_trades(
            before_runs[label]["trades"],
            after_runs[label]["trades"],
        )
        for label in base.WINDOWS
    }
    delta_metrics = _delta_metrics(before_metrics, after_metrics)
    gate4 = _gate4(delta_metrics, adjustments)
    passed = gate4["passed"]
    decision = (
        "accepted_unreduced_trend_price_extension_risk"
        if passed
        else "rejected_unreduced_trend_price_extension_risk"
    )
    interpretation = (
        "Restricting the trend price-extension top-up to unreduced signals cleared the canonical three-window gate and should be promoted only through shared sizing policy."
        if passed
        else "Restricting the trend price-extension top-up to unreduced signals did not clear the canonical three-window gate."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted trend-only price-vs-200MA extension top-up may be strongest when it is not fighting older explicit de-risking rules. "
            "Already-qualified trend extension signals with no prior risk haircut may deserve the accepted top-up, while haircut-tagged extension signals should remain at their de-risked size."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "trend_price_extension_unreduced_eligibility_gate",
        "single_causal_variable": (
            "eligibility of the accepted 1.125x trend price-vs-200MA extension top-up: all trend extension signals versus only signals with no pre-existing risk multiplier below 1.0"
        ),
        "parameters": {
            "accepted_trend_price_extension_multiplier": ACCEPTED_TREND_EXTENSION_MULTIPLIER,
            "state_definition": {
                "strategy": "trend_long",
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "requires_price_vs_200ma_extension_state": True,
                "requires_no_existing_risk_multiplier_below_1": True,
                "keeps_existing_broad_price_extension_topup": True,
            },
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "accepted broad price-vs-200MA extension top-up",
                "accepted trend extension scalar value",
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
                "exp-20260515-026": "Accepted 1.125x trend-only price-vs-200MA extension top-up; this run changes only its eligibility around pre-existing risk haircuts.",
                "exp-20260515-024_price_extension_nonconfirmation_haircut": "Rejected broad extension nonconfirmation haircut; this run does not use signal-day confirmation and only tests interaction with explicit risk haircuts.",
                "exp-20260515-020": "Rejected RS60 x price-extension overlap; this run avoids RS overlap and keeps the accepted scalar fixed.",
                "exp-20260515-022": "Rejected RS60 unextended complement because the cohort was too small.",
            },
            "why_this_branch": (
                "It uses a production-visible risk-policy interaction, not another nearby scalar, ticker cap, or LLM/Space sample-thin field."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: keep the accepted trend extension top-up only where no existing shared policy has already marked the signal as fragile."
            ),
            "2_history_check": (
                "Broad/trend extension scalars, RS overlap, and nonconfirmation variants were checked; no prior test asked whether the accepted trend extension top-up should skip explicit risk-haircut states."
            ),
            "3_single_causal_variable": "trend_price_extension_unreduced_eligibility_gate only",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, nonzero adjustments"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_027_unreduced_trend_price_extension_risk.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            "windows": base.WINDOWS,
        },
        "gate1": {
            "baseline_source": "rerun inside this script using current accepted shared policy and docs/backtesting.md fixed snapshots",
            "baseline_metrics": before_metrics,
            "baseline_aggregate": delta_metrics["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "risk_engine price_vs_200ma_extension_state",
                "risk_engine sector",
                "portfolio_engine strategy",
                "portfolio_engine existing *_risk_multiplier_applied fields",
                "portfolio_engine max_position_pct_applied",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": delta_metrics["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta": delta_metrics["aggregate_delta"][
                "signals_survived_sum"
            ],
            "minimum_after_survival_rate": delta_metrics["aggregate_after"][
                "survival_rate_min"
            ],
            "passed": delta_metrics["aggregate_after"]["survival_rate_min"] >= 0.05,
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "expected_value_score_delta": delta_metrics["aggregate_delta"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": delta_metrics["aggregate_delta"]["total_pnl_sum"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, move the no-prior-haircut eligibility check into shared portfolio_engine.py and add focused production/backtest parity tests before live orders change."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "Do not narrow the accepted trend price-extension top-up around prior risk haircuts on these frozen windows without forward attribution or a new production-visible fragility state."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_027_unreduced_trend_price_extension_risk.py",
            "data/experiments/exp-20260515-027/unreduced_trend_price_extension_risk.json",
            "docs/experiments/logs/exp-20260515-027_unreduced_trend_price_extension_risk.json",
            "docs/experiments/tickets/exp-20260515-027_unreduced_trend_price_extension_risk.json",
            "docs/experiments/artifacts/exp-20260515-027_unreduced_trend_price_extension_risk.md",
            "docs/experiment_log.jsonl",
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
            "title": "Unreduced trend price-extension risk",
            "decision": payload["decision"],
            "summary": (
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
