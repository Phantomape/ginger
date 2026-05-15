"""exp-20260515-024: price-extension nonconfirmation risk haircut.

Tests one production-visible allocation state on the accepted core stack:
already-qualified trend/breakout stock signals where:

* price_vs_200ma_extension_state is true; and
* signal_day_ticker_outperformed_spy is false.

The accepted price-vs-200MA extension top-up rewards slow-trend strength. This
scout asks whether the same state should be partially haircut when the signal
day lacks idiosyncratic confirmation versus SPY. It does not change entries,
filters, ranking, exits, targets, universe, LLM/news behavior, heat, or slots.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260515-024"
EXPERIMENT_SLUG = "price_extension_nonconfirmation_haircut"
MULTIPLIER_KEY = "price_extension_nonconfirmation_haircut_multiplier_applied"
HAIRCUT_SWEEP = [0.975, 0.95, 0.90, 0.85, 0.75]
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_HAIRCUT_MULTIPLIER = 1.0
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


def _price_extension_nonconfirmation_state(sig: dict[str, Any]) -> bool:
    return (
        sig.get("strategy") in {"trend_long", "breakout_long"}
        and sig.get("sector") not in EXCLUDED_SECTORS
        and sig.get("price_vs_200ma_extension_state") is True
        and sig.get("signal_day_ticker_outperformed_spy") is False
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
    if entry <= 0:
        return sizing
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["price_extension_nonconfirmation_baseline_shares"] = shares
    out["price_extension_nonconfirmation_new_shares"] = new_shares
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
            if (
                _price_extension_nonconfirmation_state(sig)
                and sizing.get("shares_to_buy")
            ):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    CURRENT_HAIRCUT_MULTIPLIER,
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
                            "momentum_60d_pct": sig.get("momentum_60d_pct"),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "signal_day_ticker_outperformed_spy": sig.get(
                                "signal_day_ticker_outperformed_spy"
                            ),
                            "ticker_ret20_minus_spy_pct": sig.get(
                                "ticker_ret20_minus_spy_pct"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "max_position_pct_applied": sizing.get(
                                "max_position_pct_applied"
                            ),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
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
    global CURRENT_HAIRCUT_MULTIPLIER
    CURRENT_HAIRCUT_MULTIPLIER = multiplier

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
        "haircut_multiplier": multiplier,
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


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in candidates if row["passed"]]
    pool = passing if passing else candidates
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["delta_metrics"]["aggregate_delta"]["expected_value_score_sum"]),
            float(row["delta_metrics"]["aggregate_delta"]["total_pnl_sum"]),
        ),
    )


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                mult=row["haircut_multiplier"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )
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
            f"# {EXPERIMENT_ID} Price Extension Nonconfirmation Haircut",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing haircut for already-qualified trend/breakout non-ETF/non-commodity stocks with `price_vs_200ma_extension_state=true` and `signal_day_ticker_outperformed_spy=false`.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected multiplier: `{payload['parameters']['selected_haircut_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
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
        for multiplier in HAIRCUT_SWEEP
    ]
    selected = _select_candidate(candidates)
    selected_delta = selected["delta_metrics"]["aggregate_delta"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_price_extension_nonconfirmation_haircut"
    )
    interpretation = (
        "Price-vs-200MA extension nonconfirmation cleared the canonical three-window gate as a haircut and should be promoted only through shared sizing policy."
        if selected["passed"]
        else "Price-vs-200MA extension nonconfirmation did not clear the canonical three-window gate as a sizing haircut."
    )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted price-vs-200MA extension state captures slow-trend strength, "
            "but extension signals that fail to outperform SPY on the signal day may "
            "represent crowded beta continuation rather than idiosyncratic breakout. "
            "A small post-sizing haircut may improve expected value without adding a filter."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "price_extension_nonconfirmation_haircut_multiplier",
        "single_causal_variable": (
            "post-sizing haircut multiplier for trend/breakout stock signals where price_vs_200ma_extension_state=true and signal_day_ticker_outperformed_spy=false"
        ),
        "parameters": {
            "haircut_multiplier_sweep": HAIRCUT_SWEEP,
            "selected_haircut_multiplier": selected["haircut_multiplier"],
            "requires_strategy": ["trend_long", "breakout_long"],
            "requires_price_vs_200ma_extension_state": True,
            "requires_signal_day_ticker_outperformed_spy": False,
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "accepted price_vs_200ma_extension state definition",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": [
                "exp-20260515-018 accepted price-vs-200MA extension as a standalone slow-trend allocation top-up.",
                "exp-20260515-020 rejected the RS60 x price-vs-200MA extension overlap top-up.",
                "exp-20260515-022 rejected the RS60-unextended complement top-up.",
                "exp-20260513-109 rejected clean-SPY-leader nonconfirmation haircut; this run is extension-specific and not a broad clean-SPY mirror.",
                "exp-20260513-011 rejected signal-day SPY-excess margin top-up; this run tests absence of confirmation only inside the accepted extension state.",
                "LLM/SEC/Space branches were avoided because recent records show data, field, or sample limits for those alpha paths.",
            ],
            "direct_duplicate_check": (
                "No prior price_vs_200ma_extension_state x signal_day_ticker_outperformed_spy=false haircut experiment was found."
            ),
            "why_this_branch": (
                "It follows the playbook's allocation-before-filtering priority, uses a production-visible field, and tests a different direction after overlap top-ups failed."
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "date_range": base.WINDOWS,
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Risk allocation: reduce size for accepted price-vs-200MA extension signals that lack signal-day SPY outperformance confirmation."
            ),
            "2_prior_similar_experiments": (
                "The extension component was accepted, overlap/complement top-ups were rejected, and no direct extension-specific nonconfirmation haircut was found."
            ),
            "3_single_causal_variable": (
                "price_extension_nonconfirmation_haircut_multiplier; state definitions and all other sizing rules stay fixed."
            ),
            "4_success_criteria": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, max drawdown drift <= 0.5 pp, survival >= 5%, adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_024_price_extension_nonconfirmation_haircut.py"
            ),
        },
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
            "baseline_note": (
                "Current working tree baseline includes the accepted shared slow-trend allocation stack through exp-20260515-018."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine price_vs_200ma_extension_state",
                "risk_engine signal_day_ticker_outperformed_spy",
                "portfolio_engine sizing shares_to_buy",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": selected_delta["signals_generated_sum"],
            "signals_survived_delta": selected_delta["signals_survived_sum"],
            "minimum_after_survival_rate": selected["delta_metrics"][
                "aggregate_after"
            ]["survival_rate_min"],
            "passed": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ]
            >= 0.05,
        },
        "gate4": {
            "passed": selected["passed"],
            "improved_windows": selected["improved_windows"],
            "regressed_windows": selected["regressed_windows"],
            "adjusted_signal_count": selected["adjusted_signal_count"],
            "max_drawdown_worse": selected["max_drawdown_worse"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": selected["drawdown_guardrail_passed"],
        },
        "expected_value_score_delta": selected_delta["expected_value_score_sum"],
        "total_pnl_delta": selected_delta["total_pnl_sum"],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": None
        if selected["passed"]
        else (
            "Do not retry price-extension nonconfirmation haircuts on the frozen windows without new forward attribution or a distinct production-visible failure discriminator."
        ),
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Recent LLM soft-ranking records remain data-limited; this scout used deterministic shared fields instead."
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
        "related_files": [
            str(artifact_path.relative_to(base.REPO_ROOT)),
            str(log_path.relative_to(base.REPO_ROOT)),
            str(ticket_path.relative_to(base.REPO_ROOT)),
            str(md_path.relative_to(base.REPO_ROOT)),
            "quant/experiments/exp_20260515_024_price_extension_nonconfirmation_haircut.py",
        ],
        "sweep_summary": [
            {
                "haircut_multiplier": row["haircut_multiplier"],
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
                "drawdown_guardrail_passed": row["drawdown_guardrail_passed"],
            }
            for row in candidates
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)

    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "experiment_id": EXPERIMENT_ID,
            "slug": EXPERIMENT_SLUG,
            "status": decision,
            "decision": decision,
            "changed_variable": payload["changed_variable"],
            "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
            "json": str(artifact_path.relative_to(base.REPO_ROOT)),
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "gate4_passed": payload["gate4"]["passed"],
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
                "selected_haircut_multiplier": result["haircut_multiplier"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "sweep_summary": result["sweep_summary"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
