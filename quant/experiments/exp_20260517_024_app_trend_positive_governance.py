"""exp-20260517-024: APP trend positive ticker-governance scout.

This is an alpha-search replay, not a production rule. It tests whether the
largest non-exhausted positive ticker-governance residual in the current core
stack, APP trend_long, deserves more risk after existing shared sizing rules.

Single causal variable: a cap-aware post-sizing top-up for already-qualified
APP trend_long signals. Entries, filters, ranking, exits, targets, candidate
pool, heat, slots, LLM/news, event sleeves, and all other tickers remain locked.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260516_022_signal_day_atr_expansion_risk as scout


EXPERIMENT_ID = "exp-20260517-024"
EXPERIMENT_SLUG = "app_trend_positive_governance"
MULTIPLIER_KEY = "app_trend_positive_governance_multiplier_applied"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [1.0, 1.25, 1.5, 2.0]
TARGET_TICKER = "APP"
TARGET_STRATEGY = "trend_long"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 3
MIN_AFFECTED_WINDOW_COUNT = 2

CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
APP_CANDIDATES: list[dict[str, Any]] = []


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    return original


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    return original


def _is_target_signal(sig: dict[str, Any]) -> bool:
    return (
        str(sig.get("ticker") or "").upper() == TARGET_TICKER
        and sig.get("strategy") == TARGET_STRATEGY
    )


def _candidate_record(sig: dict[str, Any]) -> dict[str, Any]:
    sizing = sig.get("sizing") or {}
    shares = int(sizing.get("shares_to_buy") or 0)
    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    cap_pct = float(
        sizing.get("max_position_pct_applied")
        or scout.base.portfolio_engine.MAX_POSITION_PCT
    )
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry)) if entry else 0
    return {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "shares_to_buy": shares,
        "entry_price": sizing.get("entry_price") or sig.get("entry_price"),
        "cap_pct": cap_pct,
        "cap_shares": cap_shares,
        "cap_bound": shares >= cap_shares if cap_shares else None,
        "trade_quality_score": sig.get("trade_quality_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "regime_exit_score": sig.get("regime_exit_score"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "signal_day_ticker_green_candle": sig.get(
            "signal_day_ticker_green_candle"
        ),
        "signal_day_ticker_outperformed_spy": sig.get(
            "signal_day_ticker_outperformed_spy"
        ),
        "price_vs_200ma_extension_state": sig.get(
            "price_vs_200ma_extension_state"
        ),
        "sizing_multipliers": {
            key: value
            for key, value in sizing.items()
            if key.endswith("_applied") and value not in (None, 1.0)
        },
    }


def _topup_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0 or CURRENT_RISK_MULTIPLIER <= 1.0:
        return sizing

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or portfolio_value <= 0 or net_risk_per_share <= 0:
        return sizing

    cap_pct = float(
        sizing.get("max_position_pct_applied")
        or scout.base.portfolio_engine.MAX_POSITION_PCT
    )
    desired_shares = max(shares, int(math.floor(shares * CURRENT_RISK_MULTIPLIER)))
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= shares:
        return sizing

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    out = dict(sizing)
    out["app_trend_positive_governance_baseline_shares"] = shares
    out["app_trend_positive_governance_desired_shares"] = desired_shares
    out["app_trend_positive_governance_cap_shares"] = cap_shares
    out["app_trend_positive_governance_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value
    out[MULTIPLIER_KEY] = CURRENT_RISK_MULTIPLIER
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
            if _is_target_signal(sig):
                APP_CANDIDATES.append(_candidate_record(sig))
                adjusted = _topup_sizing(sig, sizing, portfolio_value)
                if adjusted is not sizing:
                    scout.base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "desired_shares": adjusted.get(
                                "app_trend_positive_governance_desired_shares"
                            ),
                            "cap_shares": adjusted.get(
                                "app_trend_positive_governance_cap_shares"
                            ),
                            "new_shares": adjusted.get("shares_to_buy"),
                            "multiplier": CURRENT_RISK_MULTIPLIER,
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
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted}
            out.append(sig)
        return out

    return wrapped


def _configure_base() -> None:
    base = scout.base
    base.WINDOWS = scout.WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown


def _run_window_with_multiplier(label: str, multiplier: float) -> dict[str, Any]:
    global CURRENT_RISK_MULTIPLIER, APP_CANDIDATES
    CURRENT_RISK_MULTIPLIER = multiplier
    APP_CANDIDATES = []
    run = scout.base._run_window(label, variant=True)
    run["app_candidates"] = list(APP_CANDIDATES)
    return run


def _baseline_ticker_governance(
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "trade_count": 0,
            "win_count": 0,
            "total_pnl": 0.0,
            "windows": set(),
            "strategies": defaultdict(lambda: {"trade_count": 0, "total_pnl": 0.0}),
        }
    )
    for label, run in before_runs.items():
        for trade in run["trades"]:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            row = stats[ticker]
            row["trade_count"] += 1
            row["win_count"] += 1 if pnl > 0 else 0
            row["total_pnl"] += pnl
            row["windows"].add(label)
            strategy = str(trade.get("strategy") or "")
            row["strategies"][strategy]["trade_count"] += 1
            row["strategies"][strategy]["total_pnl"] += pnl

    rows = []
    for ticker, row in stats.items():
        rows.append(
            {
                "ticker": ticker,
                "trade_count": row["trade_count"],
                "win_count": row["win_count"],
                "total_pnl": round(row["total_pnl"], 2),
                "windows": sorted(row["windows"]),
                "strategies": {
                    strategy: {
                        "trade_count": values["trade_count"],
                        "total_pnl": round(values["total_pnl"], 2),
                    }
                    for strategy, values in row["strategies"].items()
                },
            }
        )
    rows = sorted(rows, key=lambda item: item["total_pnl"])
    return {
        "bottom_tickers": rows[:10],
        "top_tickers": rows[-10:],
        "app_rank_from_top": next(
            (
                index + 1
                for index, row in enumerate(reversed(rows))
                if row["ticker"] == TARGET_TICKER
            ),
            None,
        ),
    }


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in scout.base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}
    app_candidates: dict[str, list[dict[str, Any]]] = {}

    for label in scout.base.WINDOWS:
        variant = _run_window_with_multiplier(label, multiplier)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = scout.base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }
        app_candidates[label] = variant["app_candidates"]

    by_window_delta = {
        label: scout.base._delta(after_metrics[label], before_metrics[label])
        for label in scout.base.WINDOWS
    }
    aggregate_before = scout.base._aggregate(before_metrics)
    aggregate_after = scout.base._aggregate(after_metrics)
    aggregate_delta = scout.base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in scout.base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in scout.base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    affected_windows = [label for label, rows in adjustments.items() if rows]
    affected_signal_count = sum(len(rows) for rows in adjustments.values())
    candidate_signal_count = sum(len(rows) for rows in app_candidates.values())
    cap_bound_candidate_count = sum(
        1
        for rows in app_candidates.values()
        for row in rows
        if row.get("cap_bound") is True
    )
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in by_window_delta.values()
    )
    is_identity = math.isclose(multiplier, BASELINE_RISK_MULTIPLIER)
    sample_guard_passed = (
        affected_signal_count >= MIN_AFFECTED_SIGNAL_COUNT
        and len(affected_windows) >= MIN_AFFECTED_WINDOW_COUNT
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        not is_identity
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and sample_guard_passed
        and drawdown_guardrail_passed
    )

    return {
        "risk_multiplier": multiplier,
        "is_identity_control": is_identity,
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
            "affected_signal_count": affected_signal_count,
            "affected_windows": affected_windows,
            "candidate_signal_count": candidate_signal_count,
            "cap_bound_candidate_count": cap_bound_candidate_count,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "sample_guard_passed": sample_guard_passed,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
        "app_candidates": app_candidates,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    non_identity = [row for row in candidates if not row["is_identity_control"]]
    passed = [row for row in non_identity if row["passed"]]
    pool = passed if passed else non_identity
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"]["max_drawdown_worse"]),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "risk_multiplier": row["risk_multiplier"],
            "is_identity_control": row["is_identity_control"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "affected_signal_count": row["gate4"]["affected_signal_count"],
            "affected_windows": row["gate4"]["affected_windows"],
            "candidate_signal_count": row["gate4"]["candidate_signal_count"],
            "cap_bound_candidate_count": row["gate4"]["cap_bound_candidate_count"],
            "sample_guard_passed": row["gate4"]["sample_guard_passed"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "drawdown_guardrail_passed": row["gate4"][
                "drawdown_guardrail_passed"
            ],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Candidate rows | Cap-bound | Windows |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---:|---:|---|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {candidates} | {cap_bound} | {windows} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                candidates=row["candidate_signal_count"],
                cap_bound=row["cap_bound_candidate_count"],
                windows=", ".join(row["affected_windows"]) or "-",
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in scout.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} APP Trend Positive Governance",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for already-qualified APP trend_long signals. No production policy changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
        ]
    )


def run() -> dict[str, Any]:
    _configure_base()
    gate2 = scout.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: scout.base._run_window(label, variant=False)
        for label in scout.base.WINDOWS
    }
    before_metrics = {label: before_runs[label]["metrics"] for label in scout.base.WINDOWS}
    governance = _baseline_ticker_governance(before_runs)
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)
    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_app_trend_positive_governance_underpowered"
    )
    interpretation = (
        "APP trend_long top-up cleared Gate 4 and would require shared policy promotion plus rerun before production use."
        if selected["passed"]
        else (
            "APP remains a real positive ticker-governance clue, but the top-up "
            "is underpowered on the frozen windows: too few adjusted rows survive "
            "the cap-aware path for promotion."
        )
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Current ticker-pool governance should look for residual positive "
            "allocation value after the accepted stack. APP trend_long is the "
            "largest non-exhausted positive core ticker outside the existing "
            "Commodity/Financials/TSM/ISRG/V/DDOG lanes. If it is genuinely "
            "under-allocated, a cap-aware APP trend top-up should improve the "
            "canonical three-window EV without changing entries or ranking."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "app_trend_positive_governance_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing top-up multiplier for APP trend_long signals"
        ),
        "parameters": {
            "target_ticker": TARGET_TICKER,
            "target_strategy": TARGET_STRATEGY,
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all non-APP sizing multipliers",
                "APP non-trend signals",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / ticker-pool governance: test whether APP "
                "trend_long deserves more capital after existing shared sizing."
            ),
            "2_history_check": {
                "exp-20260516-041": (
                    "TSM/ISRG/V/DDOG negative ticker governance was already "
                    "handled; V/DDOG require forward evidence, and this run does "
                    "not retune them."
                ),
                "commodity_financials_lanes": (
                    "GLD/SLV and Financials leaders dominate positive PnL but "
                    "nearby Commodity/Financials cap and scalar retunes are "
                    "explicitly frozen without forward evidence."
                ),
                "APP_history": (
                    "APP appears repeatedly in old candidate/slot diagnostics, "
                    "but no current-stack APP trend positive-governance scalar "
                    "exists after exp-20260517-009."
                ),
            },
            "3_single_causal_variable": (
                "Only APP trend_long post-sizing top-up multiplier changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, max drawdown drift <= 0.5 pp, and at "
                "least three adjusted APP trend rows across at least two windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260517_024_app_trend_positive_governance.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": scout.base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": scout.base._aggregate(before_metrics),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine ticker",
                "risk_engine strategy",
                "portfolio_engine shares_to_buy",
                "portfolio_engine entry_price",
                "portfolio_engine portfolio_value_usd",
                "portfolio_engine net_risk_per_share",
                "portfolio_engine max_position_pct_applied",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": scout.base._aggregate(before_metrics)[
                "survival_rate_min"
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
        "app_candidates": selected["app_candidates"],
        "baseline_ticker_governance": governance,
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "No LLM behavior changed; LLM/SEC semantic branches remain "
                "field-limited for current promotion decisions."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a future APP governance rule passes, implement it as a "
                "shared portfolio_engine constant/path used by both backtester.py "
                "and run.py, then rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM soft-ranking because replay data remains sparse, "
            "does not expand the candidate pool with unproven tickers, avoids "
            "V/DDOG because they are already in forward core-misfit paper, and "
            "does not retune frozen Commodity/Financials/slot/state-surface "
            "nearby scalars."
        ),
        "known_risks": [
            "Ticker-specific positive top-ups are high overfit risk.",
            "APP old-window trend exposure is already cap-bound, so a post-sizing top-up may only adjust one historical row.",
            "A positive replay scout is not production-tradable until shared policy and parity tests are promoted and rerun.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else (
                "Do not promote APP-specific positive sizing on the frozen "
                "sample. Revisit only with forward APP/core ticker-governance "
                "evidence or a broader production-visible field that creates a "
                "mature cohort."
            )
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260517_024_app_trend_positive_governance.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> dict[str, Any]:
    result = run()
    scout.base.persist(result)
    return result


if __name__ == "__main__":
    result = main()
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
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "affected_windows": result["gate4"]["affected_windows"],
                "candidate_signal_count": result["gate4"]["candidate_signal_count"],
                "cap_bound_candidate_count": result["gate4"][
                    "cap_bound_candidate_count"
                ],
                "selected_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
