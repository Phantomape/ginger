"""exp-20260513-026: sector-confirmed green gap-cushion risk allocation.

Tests one production-visible core allocation state: already-qualified
trend/breakout signals with accepted own-green signal-day confirmation, a
positive signal-day sector proxy candle, and the existing non-tight-stop gap
cushion. This is a cap-aware post-sizing scout, not an entry filter, ranking
change, exit change, universe change, LLM change, or production default.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260513-026"
EXPERIMENT_SLUG = "green_sector_cushion_risk"
MULTIPLIER_KEY = "green_sector_cushion_risk_multiplier_applied"
RISK_MULTIPLIER_SWEEP = [1.025, 1.05, 1.075, 1.10, 1.15]
GAP_WARNING_MIN_CUSHION_PCT = 0.02
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CURRENT_RISK_MULTIPLIER = 1.0


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    def wrapped(
        ticker: str,
        ohlcv_data: Any,
        earnings_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        features = original(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        features = dict(features)
        features["signal_day_open_close_return_pct"] = (
            base._signal_day_open_close_return(ohlcv_data)
        )
        return features

    return wrapped


def _is_green_sector_cushion_state(sig: dict[str, Any]) -> bool:
    gap_vulnerability = sig.get("gap_vulnerability_pct")
    sector_ret = sig.get("signal_day_sector_proxy_open_close_return_pct")
    return (
        sig.get("strategy") in {"trend_long", "breakout_long"}
        and sig.get("signal_day_ticker_green_candle") is True
        and isinstance(sector_ret, (int, float))
        and sector_ret > 0
        and isinstance(gap_vulnerability, (int, float))
        and gap_vulnerability >= GAP_WARNING_MIN_CUSHION_PCT
    )


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
            sector = sig.get("sector")
            proxy = base.SECTOR_PROXY.get(str(sector or ""))
            proxy_ret = None
            if proxy:
                proxy_ret = (features_dict.get(proxy) or {}).get(
                    "signal_day_open_close_return_pct"
                )
            sig["signal_day_sector_proxy"] = proxy
            sig["signal_day_sector_proxy_open_close_return_pct"] = proxy_ret
            sig["green_sector_cushion_state"] = _is_green_sector_cushion_state(sig)
            sig["green_sector_cushion_min_gap_pct"] = GAP_WARNING_MIN_CUSHION_PCT
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
    out["green_sector_cushion_baseline_shares"] = shares
    out["green_sector_cushion_desired_shares"] = desired_shares
    out["green_sector_cushion_cap_shares"] = cap_shares
    out["green_sector_cushion_new_shares"] = new_shares
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
            if sig.get("green_sector_cushion_state") and sizing.get("shares_to_buy"):
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
                            "sector_proxy": sig.get("signal_day_sector_proxy"),
                            "sector_proxy_open_close_return_pct": sig.get(
                                "signal_day_sector_proxy_open_close_return_pct"
                            ),
                            "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "signal_day_ticker_open_close_return_pct": sig.get(
                                "signal_day_ticker_open_close_return_pct"
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
            f"# {EXPERIMENT_ID} Green Sector-Cushion Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals whose accepted signal-day own candle is green, whose signal-day sector proxy candle is positive, and whose existing `gap_vulnerability_pct` is outside the tight-gap warning zone. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
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
            "Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` implementation plus attribution-key parity before live/default behavior changes.",
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

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
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
        else "rejected_green_sector_cushion_risk"
    )
    interpretation = (
        "Sector-confirmed green gap-cushion risk top-up cleared the canonical three-window gate and requires shared policy implementation before production use."
        if passed
        else "Sector-confirmed green gap-cushion risk top-up did not clear the canonical three-window gate; do not promote this frozen-window own-green overlay without forward execution-risk attribution."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted own-green follow-through signal may have better replacement value when the sector proxy also closes green on the signal day and the stop has at least the existing 2% gap cushion. This should preserve the positive green-candle edge while reducing the drawdown fragility seen in broader green overlays."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "green_sector_cushion_risk_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing risk top-up for trend/breakout signals where signal_day_ticker_green_candle is true, signal-day sector proxy return is > 0, and gap_vulnerability_pct >= 0.02"
        ),
        "parameters": {
            "state_definition": {
                "strategies": ["trend_long", "breakout_long"],
                "signal_day_ticker_green_candle": True,
                "signal_day_sector_proxy_open_close_return_pct": "> 0",
                "gap_vulnerability_pct": ">= existing gap_warning threshold 0.02",
                "sector_proxy": base.SECTOR_PROXY,
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
            "1_alpha_hypothesis": (
                "core risk allocation using accepted own-green confirmation, same-day sector confirmation, and the existing gap-cushion state"
            ),
            "2_history_check": {
                "exp-20260513-007": (
                    "accepted own-green 1.05x top-up; this keeps that baseline locked and tests only an incremental sector-confirmed cushion overlay."
                ),
                "exp-20260512-107": (
                    "fixed positive sector tape alone was aggregate-positive but only moved old_thin; this adds own-green and gap-cushion confirmation instead of retrying a tape-only scalar."
                ),
                "exp-20260513-023": (
                    "green momentum deceleration improved all windows at 1.10x but failed the drawdown guardrail."
                ),
                "exp-20260513-024": (
                    "green gap-cushion improved all windows but failed drawdown; this tests sector confirmation as the new discriminator, not a nearby scalar retune."
                ),
                "llm_soft_ranking": (
                    "labeled forward data remains thin, so this run avoids LLM scoring."
                ),
                "space_profile_scalars": (
                    "recent frozen-sample Space profile slicing is over-mined; this run stays in core allocation."
                ),
            },
            "3_single_causal_variable": (
                "green_sector_cushion_risk_multiplier with fixed production-visible state definition"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_026_green_sector_cushion_risk.py"
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
                "feature_layer signal_day_open_close_return_pct",
                "risk_engine signal_day_ticker_green_candle",
                "risk_engine gap_vulnerability_pct",
                "risk_engine sector",
                "risk_engine injected signal_day_sector_proxy_open_close_return_pct",
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
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "Use forward own-green execution-risk attribution or a different production-visible core allocation state before retrying this overlay family."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_026_green_sector_cushion_risk.py",
            "data/experiments/exp-20260513-026/green_sector_cushion_risk.json",
            "experiments/logs/exp-20260513-026.json",
            "experiments/tickets/exp-20260513-026.json",
            "experiments/artifacts/exp-20260513-026_green_sector_cushion_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited; SEC semantic fields are missing; Space frozen-sample profile scalars are over-mined. This tests a production-visible core allocation state without adding ticker noise or a new filter."
        ),
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
            },
            indent=2,
            sort_keys=True,
        )
    )
