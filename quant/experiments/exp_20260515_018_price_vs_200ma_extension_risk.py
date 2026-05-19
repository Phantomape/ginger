"""exp-20260515-018: price-vs-200MA extension core risk allocation.

Tests one production-visible allocation state on the accepted core stack:
already-qualified trend/breakout stock signals whose same-day
``price_vs_200ma_pct`` is in the top quartile of feature-complete
non-ETF/non-commodity stocks.

This is a cap-aware post-sizing risk top-up scout, not an entry filter,
ranking change, exit change, universe change, LLM/news change, or production
default change.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260515-018"
EXPERIMENT_SLUG = "price_vs_200ma_extension_risk"
MULTIPLIER_KEY = "price_vs_200ma_extension_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.025, 1.05, 1.10, 1.15]
EXTENSION_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_RISK_MULTIPLIER = 1.0


def _finite_float(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


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


def _extension_cutoff(features_dict: dict[str, dict[str, Any]]) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        sector = base.risk_engine.SECTOR_MAP.get(ticker, "Unknown")
        extension = _finite_float((features or {}).get("price_vs_200ma_pct"))
        if sector in EXCLUDED_SECTORS:
            continue
        if extension is not None:
            values.append(extension)
    if not values:
        return None
    values.sort()
    index = max(0, math.ceil(len(values) * (1.0 - EXTENSION_FRACTION)) - 1)
    return values[index]


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = _extension_cutoff(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "")
            features = features_dict.get(ticker) or {}
            extension = _finite_float(features.get("price_vs_200ma_pct"))
            eligible = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sig.get("sector") not in EXCLUDED_SECTORS
                and extension is not None
                and isinstance(cutoff, (int, float))
                and extension >= float(cutoff)
            )
            sig["price_vs_200ma_pct"] = extension
            sig["price_vs_200ma_extension_cutoff"] = cutoff
            sig["price_vs_200ma_extension_state"] = bool(eligible)
        return enriched

    return wrapped


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
    out["price_vs_200ma_extension_baseline_shares"] = shares
    out["price_vs_200ma_extension_desired_shares"] = desired_shares
    out["price_vs_200ma_extension_cap_shares"] = cap_shares
    out["price_vs_200ma_extension_new_shares"] = new_shares
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
            if sig.get("price_vs_200ma_extension_state") and sizing.get("shares_to_buy"):
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
                            "price_vs_200ma_pct": sig.get("price_vs_200ma_pct"),
                            "price_vs_200ma_extension_cutoff": sig.get(
                                "price_vs_200ma_extension_cutoff"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
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
            1 if row["passed"] else 0,
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
            "drawdown_guardrail_passed": row["gate4"]["drawdown_guardrail_passed"],
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
            "| {mult:.3f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
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
            f"# {EXPERIMENT_ID} Price-vs-200MA Extension Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose `price_vs_200ma_pct` is in the same-day top quartile of feature-complete non-ETF/non-commodity stocks. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
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
            "Production impact: replay-only scout. Positive promotion requires shared feature/risk/sizing code and attribution-key parity before production-visible behavior changes.",
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
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_price_vs_200ma_extension_risk"
    )
    interpretation = (
        "Price-vs-200MA top-quartile core stock signals cleared the canonical three-window gate and should be promoted only through shared production/backtest policy."
        if passed
        else "Price-vs-200MA top-quartile extension did not clear the canonical three-window gate; do not promote this state variable on the frozen windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "After nearby cap/scalar retries became low priority, the next core "
            "allocation question is whether an independent slow-trend quality "
            "state still adds information. Already-qualified trend/breakout "
            "stocks that are in the top quartile of price distance above their "
            "200-day moving average may represent stronger institutional trend "
            "leadership and deserve a small cap-aware sizing top-up."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "price_vs_200ma_extension_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout stock signals whose PIT price_vs_200ma_pct is in the same-day top quartile"
        ),
        "parameters": {
            "state_definition": {
                "strategies": ["trend_long", "breakout_long"],
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
                "price_vs_200ma_pct": "top 25% of feature-complete non-ETF/non-commodity stocks on that signal day",
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
                "MAX_POSITIONS",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "RS20/RS60/own_green": (
                    "Accepted or exhausted momentum confirmations; this uses a slower 200MA-distance trend-quality state, not another RS scalar."
                ),
                "price_vs_200ma_capacity": (
                    "Prior pct-from-200MA work was broad capacity/slot gating; this keeps the candidate set and slots fixed and only tests post-sizing allocation."
                ),
                "sector_etf_candidate_pool": (
                    "exp-20260515-017 showed simple candidate-pool expansion did not beat the core; this keeps the core pool fixed."
                ),
                "LLM_soft_ranking": (
                    "Avoided because downstream LLM ranking attribution remains data-limited."
                ),
            },
            "why_this_branch": (
                "It matches the playbook's allocation-before-filtering prior and uses fields already present in the production feature layer."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: top-quartile price-vs-200MA extension may identify stronger trend leaders among already-qualified core signals."
            ),
            "2_history_check": (
                "Similar broad pct-from-200MA slot/capacity experiments failed, but no current-log top-quartile price-vs-200MA post-sizing scout was found; recent LLM/SEC/Space/candidate-pool branches are field- or sample-limited."
            ),
            "3_single_causal_variable": (
                "price_vs_200ma_extension_risk_multiplier with a fixed cross-sectional top-quartile state definition."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_018_price_vs_200ma_extension_risk.py"
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
            "baseline_note": (
                "Current working tree baseline includes accepted exp-20260515-013 clean-SPY cap-only RS20 cap promotion."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "feature_layer price_vs_200ma_pct",
                "risk_engine sector",
                "portfolio_engine max_position_pct_applied",
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
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement price-vs-200MA extension state and sizing top-up in shared risk/portfolio modules called by both run.py and backtester.py."
            ),
        },
        "production_impact_closeout": {
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
        else (
            "Do not retry price-vs-200MA extension overlays on frozen windows without forward attribution or a different production-visible trend-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260515_018_price_vs_200ma_extension_risk.py",
            "data/experiments/exp-20260515-018/price_vs_200ma_extension_risk.json",
            "experiments/logs/exp-20260515-018_price_vs_200ma_extension_risk.json",
            "experiments/tickets/exp-20260515-018_price_vs_200ma_extension_risk.json",
            "experiments/artifacts/exp-20260515-018_price_vs_200ma_extension_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def _upsert_jsonl_by_slug(path: Any, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            same_price_experiment = (
                row.get("experiment_id") == EXPERIMENT_ID
                and row.get("changed_variable")
                == "price_vs_200ma_extension_risk_multiplier"
            )
            if same_price_experiment:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        base.REPO_ROOT
        / "experiments"
        / "logs"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.json"
    )
    ticket_path = (
        base.REPO_ROOT
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "slug": EXPERIMENT_SLUG,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
        "json": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl_by_slug(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_risk_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
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
