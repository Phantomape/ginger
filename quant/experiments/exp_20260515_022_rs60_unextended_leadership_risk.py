"""exp-20260515-022: RS60 unextended leadership risk allocation.

Tests one production-visible allocation state on the accepted core stack:
already-qualified trend/breakout stock signals where:

* rs60_top_quintile_state is true; and
* price_vs_200ma_pct is below the same-day top-quartile extension cutoff.

The prior overlap scout (exp-20260515-020) showed that adding another top-up
to RS60 leaders already in the most extended price-vs-200MA bucket was not
robust. This tests the complementary "strong but less extended" state, as a
cap-aware post-sizing risk top-up only.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260515-022"
EXPERIMENT_SLUG = "rs60_unextended_leadership_risk"
MULTIPLIER_KEY = "rs60_unextended_leadership_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.0125, 1.025, 1.05, 1.075, 1.10]
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


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
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


def _finite_float(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def _rs60_unextended_state(sig: dict[str, Any]) -> bool:
    price_vs_200ma = _finite_float(sig.get("price_vs_200ma_pct"))
    extension_cutoff = _finite_float(sig.get("price_vs_200ma_extension_cutoff"))
    return (
        sig.get("strategy") in {"trend_long", "breakout_long"}
        and sig.get("sector") not in EXCLUDED_SECTORS
        and sig.get("rs60_top_quintile_state") is True
        and price_vs_200ma is not None
        and extension_cutoff is not None
        and price_vs_200ma < extension_cutoff
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
    out["rs60_unextended_leadership_baseline_shares"] = shares
    out["rs60_unextended_leadership_desired_shares"] = desired_shares
    out["rs60_unextended_leadership_cap_shares"] = cap_shares
    out["rs60_unextended_leadership_new_shares"] = new_shares
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
            if _rs60_unextended_state(sig) and sizing.get("shares_to_buy"):
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
                            "momentum_60d_pct": sig.get("momentum_60d_pct"),
                            "rs60_top_quintile_cutoff": sig.get(
                                "rs60_top_quintile_cutoff"
                            ),
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
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
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


def _run_window(label: str) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_size = base.portfolio_engine.size_signals
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    global ADJUSTMENTS
    ADJUSTMENTS = []

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
        raise RuntimeError(f"{label} variant failed: {result['error']}")
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
        variant = _run_window(label)
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
        and drawdown_guardrail_passed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
    )

    return {
        "multiplier": multiplier,
        "passed": passed,
        "improved_windows": improved,
        "regressed_windows": regressed,
        "adjusted_signal_count": adjusted_count,
        "max_drawdown_worse": round(max_drawdown_worse, 6),
        "drawdown_guardrail_passed": drawdown_guardrail_passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD | Survival | Adjusted signals |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:.4f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=after["max_drawdown_pct"],
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} RS60 Unextended Leadership Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout non-ETF/non-commodity stocks with `rs60_top_quintile_state=true` and `price_vs_200ma_pct` below the same-day top-quartile extension cutoff.",
            "",
            *rows,
            "",
            "Production impact: replay-only scout. Positive promotion requires the helper in shared `portfolio_engine.py`, attribution keys in `backtester.py`, docs parity update, and focused parity tests before live/default behavior changes.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    passing = [row for row in candidates if row["passed"]]
    if passing:
        selected = max(
            passing,
            key=lambda row: row["delta_metrics"]["aggregate_delta"][
                "expected_value_score_sum"
            ],
        )
    else:
        selected = max(
            candidates,
            key=lambda row: row["delta_metrics"]["aggregate_delta"][
                "expected_value_score_sum"
            ],
        )

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_rs60_unextended_leadership_risk"
    )
    interpretation = (
        "RS60 leaders below the top price-vs-200MA extension bucket improved the accepted core stack and should be promoted only through shared sizing policy."
        if selected["passed"]
        else "RS60 unextended leadership did not clear the canonical three-window gate as an extra allocation top-up."
    )

    now = datetime.now(timezone.utc).isoformat()
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "logs"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.json"
    )
    ticket_path = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )

    payload: dict[str, Any] = {
        **selected,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The failed RS60 x price-vs-200MA overlap scout suggests the overextended bucket may be the wrong follow-up. "
            "Already-qualified RS60 top-quintile stocks that have not entered the top price-vs-200MA extension quartile may retain leadership with more continuation room, deserving a small cap-aware post-sizing top-up."
        ),
        "change_type": "capital_allocation",
        "changed_variable": "rs60_unextended_leadership_risk_multiplier",
        "single_causal_variable": "rs60_unextended_leadership_risk_multiplier",
        "parameters": {
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["multiplier"],
            "requires_strategy": ["trend_long", "breakout_long"],
            "requires_rs60_top_quintile_state": True,
            "requires_price_vs_200ma_below_extension_cutoff": True,
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "position caps",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows with current accepted core stack.",
        "date_range": base.WINDOWS,
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Capital allocation on RS60 leaders that are not in the top price-vs-200MA extension bucket."
            ),
            "2_prior_similar_experiments": [
                "exp-20260513-030 accepted RS60 top-quintile sizing.",
                "exp-20260515-018 accepted top-quartile price-vs-200MA extension sizing.",
                "exp-20260515-020 rejected the RS60 x price-vs-200MA extension overlap top-up because it regressed the three-window gate.",
            ],
            "3_single_causal_variable": "extra post-sizing multiplier for RS60 unextended leaders only",
            "4_success_criteria": (
                "Aggregate EV and PnL positive, at least two EV-improved windows, no EV-regressed windows, max drawdown drift <= 0.5 pp, survival >= 5%, adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_022_rs60_unextended_leadership_risk.py"
            ),
        },
        "gate2_field_audit": gate2,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains sample-limited; this deterministic allocation state is replayable on fixed OHLCV snapshots."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_accepted": (
                "Implement in shared portfolio_engine/backtester attribution and add parity tests before live/default behavior changes."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "expected_value_score_delta": selected["delta_metrics"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": selected["delta_metrics"]["aggregate_delta"][
            "total_pnl_sum"
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            "If rejected, do not retry RS60/price-extension complement scalars on the frozen windows without a new production-visible drawdown or catalyst-quality discriminator."
        ),
        "related_files": [
            str(artifact_path.relative_to(base.REPO_ROOT)),
            str(log_path.relative_to(base.REPO_ROOT)),
            str(ticket_path.relative_to(base.REPO_ROOT)),
            str(md_path.relative_to(base.REPO_ROOT)),
            "quant/experiments/exp_20260515_022_rs60_unextended_leadership_risk.py",
        ],
        "sweep_summary": [
            {
                "risk_multiplier": row["multiplier"],
                "passed": row["passed"],
                "expected_value_score_delta": row["delta_metrics"][
                    "aggregate_delta"
                ]["expected_value_score_sum"],
                "total_pnl_delta": row["delta_metrics"]["aggregate_delta"][
                    "total_pnl_sum"
                ],
                "adjusted_signal_count": row["adjusted_signal_count"],
                "improved_windows": row["improved_windows"],
                "regressed_windows": row["regressed_windows"],
                "max_drawdown_worse": row["max_drawdown_worse"],
            }
            for row in candidates
        ],
    }

    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "experiment_id": EXPERIMENT_ID,
            "slug": EXPERIMENT_SLUG,
            "status": decision,
            "changed_variable": payload["changed_variable"],
            "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
            "json": str(artifact_path.relative_to(base.REPO_ROOT)),
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_action": (
                "Promote through shared policy if accepted; otherwise treat as anti-repeat evidence."
            ),
        },
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_multiplier": result["multiplier"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "adjusted_signal_count": result["adjusted_signal_count"],
                "improved_windows": result["improved_windows"],
                "regressed_windows": result["regressed_windows"],
            },
            indent=2,
            sort_keys=True,
        )
    )
