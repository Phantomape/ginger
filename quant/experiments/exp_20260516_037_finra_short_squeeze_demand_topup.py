"""exp-20260516-037: FINRA short-squeeze demand-confirmed top-up.

Alpha search on one causal variable: a cap-aware post-sizing top-up for
already-qualified trend/breakout stock signals that combine PIT-safe FINRA
top-quartile days-to-cover with production-visible demand confirmation
(RS20 entry leadership plus a signal-day green candle).

This is replay-only. A positive result must be promoted through a shared FINRA
adapter plus shared risk/sizing policy before live/default behavior changes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260516_035_finra_short_crowding_risk_haircut as finra_base


EXPERIMENT_ID = "exp-20260516-037"
EXPERIMENT_SLUG = "finra_short_squeeze_demand_topup"
MULTIPLIER_KEY = "finra_short_squeeze_demand_topup_multiplier_applied"
STATE_KEY = "finra_short_squeeze_demand_state"
SHORT_CROWDING_KEY = "finra_short_crowding_top_quartile_state"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [1.0, 1.0125, 1.025, 1.05, 1.075, 1.1]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 2


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = finra_base._daily_days_to_cover_cutoff(features_dict)
        cutoff_for_log = round(cutoff, 6) if cutoff is not None else None
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            features = features_dict.get(ticker) or {}
            row = finra_base._latest_short_row(ticker, features)
            days_to_cover = finra_base._days_to_cover_value(row)
            short_crowding = (
                sig.get("strategy") in finra_base.STATE_STRATEGIES
                and sig.get("sector") not in finra_base.EXCLUDED_SECTORS
                and days_to_cover is not None
                and cutoff is not None
                and days_to_cover >= cutoff
            )
            sig["finra_short_interest_signal_date"] = features.get(
                "finra_short_interest_signal_date"
            )
            sig["finra_short_interest_publication_date"] = (
                row.get("publication_date") if row else None
            )
            sig["finra_short_interest_settlement_date"] = (
                row.get("settlement_date") if row else None
            )
            sig["finra_days_to_cover"] = (
                round(days_to_cover, 6) if days_to_cover is not None else None
            )
            sig["finra_short_interest_change_pct"] = (
                row.get("short_interest_change_pct") if row else None
            )
            sig["finra_short_crowding_top_quartile_cutoff"] = cutoff_for_log
            sig[SHORT_CROWDING_KEY] = short_crowding
            sig[STATE_KEY] = (
                short_crowding
                and sig.get("rs20_entry_state_leader") is True
                and sig.get("signal_day_ticker_green_candle") is True
            )
        return enriched

    return wrapped


def _topup_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0 or scalar <= 1.0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or net_risk_per_share <= 0:
        return sizing
    cap_pct = float(sizing.get("max_position_pct_applied") or 0.5)
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry))
    desired_shares = max(shares, int(math.floor(shares * scalar)))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= shares:
        return sizing
    position_value = new_shares * entry
    risk_amount = new_shares * net_risk_per_share
    out = dict(sizing)
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    out["finra_short_squeeze_demand_baseline_shares"] = shares
    out["finra_short_squeeze_demand_desired_shares"] = desired_shares
    out["finra_short_squeeze_demand_cap_shares"] = cap_shares
    out["finra_short_squeeze_demand_new_shares"] = new_shares
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
            if sig.get(STATE_KEY) and sizing.get("shares_to_buy"):
                adjusted_sizing = _topup_sizing(
                    sizing,
                    finra_base.CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "signal_date": sig.get("finra_short_interest_signal_date"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "days_to_cover": sig.get("finra_days_to_cover"),
                            "top_quartile_cutoff": sig.get(
                                "finra_short_crowding_top_quartile_cutoff"
                            ),
                            "publication_date": sig.get(
                                "finra_short_interest_publication_date"
                            ),
                            "settlement_date": sig.get(
                                "finra_short_interest_settlement_date"
                            ),
                            "short_interest_change_pct": sig.get(
                                "finra_short_interest_change_pct"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "scalar": finra_base.CURRENT_RISK_MULTIPLIER,
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "core_confirmed_quality_state": sig.get(
                                "core_confirmed_quality_state"
                            ),
                            "green_decel_quality_nonconsumer_state": sig.get(
                                "green_decel_quality_nonconsumer_state"
                            ),
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                windows=", ".join(row["affected_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FINRA Short-Squeeze Demand Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout stock signals with PIT-safe FINRA top-quartile days-to-cover plus RS20 leadership and signal-day green confirmation. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected non-control multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. A positive promotion must add a shared FINRA publication-lag adapter plus shared risk/sizing attribution used by both backtester.py and run.py, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_modules() -> None:
    finra_base.EXPERIMENT_ID = EXPERIMENT_ID
    finra_base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    finra_base.MULTIPLIER_KEY = MULTIPLIER_KEY
    finra_base.STATE_KEY = STATE_KEY
    finra_base.BASELINE_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
    finra_base.RISK_MULTIPLIER_SWEEP = RISK_MULTIPLIER_SWEEP
    finra_base.MAX_DRAWDOWN_WORSE_GUARDRAIL = MAX_DRAWDOWN_WORSE_GUARDRAIL
    finra_base.MIN_AFFECTED_SIGNAL_COUNT = MIN_AFFECTED_SIGNAL_COUNT
    finra_base.MIN_AFFECTED_WINDOW_COUNT = MIN_AFFECTED_WINDOW_COUNT
    base.WINDOWS = finra_base.WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = finra_base._make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    finra_base._ensure_finra_lookup(set(base.get_universe()))
    before_runs = {
        label: finra_base._run_window_with_multiplier(
            label,
            BASELINE_RISK_MULTIPLIER,
        )
        for label in base.WINDOWS
    }
    candidates = [
        finra_base._candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = finra_base._select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_finra_short_squeeze_demand_topup"
    )
    interpretation = (
        "FINRA high days-to-cover plus RS20/own-green demand confirmation cleared the canonical three-window scout as a cap-aware short-squeeze top-up, but remains replay-only until a shared production/backtest FINRA adapter is implemented."
        if selected["passed"]
        else "FINRA high days-to-cover plus RS20/own-green demand confirmation did not clear the canonical three-window gate as a short-squeeze top-up."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The previous FINRA days-to-cover haircut failed, suggesting the "
            "high-crowding state may contain squeeze convexity rather than "
            "only risk. The squeeze thesis should stay narrow: only already-"
            "qualified trend/breakout stocks with same-day top-quartile "
            "days-to-cover and production-visible RS20 plus own-green demand "
            "confirmation receive a small cap-aware allocation top-up."
        ),
        "change_type": "capital_allocation_shadow",
        "changed_variable": "finra_short_squeeze_demand_topup_multiplier",
        "single_causal_variable": (
            "cap-aware post-sizing top-up multiplier for trend/breakout stock "
            "signals with PIT-safe FINRA top-quartile days-to-cover plus RS20 "
            "entry leadership and signal-day green confirmation"
        ),
        "parameters": {
            "state_definition": {
                "source": "FINRA official biweekly equity short-interest CSV",
                "pit_join": "latest publication_date <= signal_date",
                "short_interest_feature": "days_to_cover",
                "short_interest_cutoff": "same-day universe top quartile",
                "demand_confirmation": [
                    "rs20_entry_state_leader is true",
                    "signal_day_ticker_green_candle is true",
                ],
                "strategies": sorted(finra_base.STATE_STRATEGIES),
                "excluded_sectors": sorted(finra_base.EXCLUDED_SECTORS),
            },
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
                "all existing sizing multipliers",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
                "candidate pool",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation on a deterministic short-squeeze demand "
                "state; this follows the playbook preference for fixed "
                "candidate-set allocation and avoids LLM/SEC data limitations"
            ),
            "2_history_check": {
                "exp-20260516-035": (
                    "FINRA top-quartile days-to-cover haircut failed, clipping "
                    "late/old winners; this tests the opposite convexity thesis "
                    "only when RS20 and own-green demand confirmation are present."
                ),
                "exp-20260513-007_and_20260510-012": (
                    "Own-green and RS20 are already shared positive states; this "
                    "does not retune either scalar, it uses them as confirmation "
                    "for the orthogonal FINRA crowding field."
                ),
                "blocked_branches_avoided": (
                    "LLM/SEC semantic ranking remains field-limited; recent DTE, "
                    "ATR, Space, gap-absorption, close-location, and broad cap "
                    "retries are over-mined or rejected."
                ),
            },
            "3_single_causal_variable": (
                "finra_short_squeeze_demand_topup_multiplier with fixed PIT "
                "short-crowding plus RS20/own-green state"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, survival >= 5%, at least six affected signals across "
                "at least two windows, and max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_037_finra_short_squeeze_demand_topup.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "finra_data_coverage": finra_base._finra_coverage_summary(),
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "feature_layer signal date",
                "FINRA publication_date",
                "FINRA days_to_cover",
                "risk_engine rs20_entry_state_leader",
                "risk_engine signal_day_ticker_green_candle",
                "portfolio_engine shares_to_buy",
            ],
            "passed": gate2["passed"] and bool(finra_base.FINRA_ROWS_BY_TICKER),
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
        "sweep_summary": finra_base._sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking and SEC semantic branches remain data-limited; "
                "this deterministic FINRA plus price-demand state avoids those blockers."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add a shared FINRA publication-lag adapter/cache and "
                "shared risk_engine/portfolio_engine state used by both backtester.py "
                "and run.py, then rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC soft-ranking because archived semantic fields are "
            "sparse, avoids Space and source-tilt nearby retries after recent "
            "sample/drawdown failures, avoids DTE/ATR/close-location/gap branches "
            "with explicit do-not-repeat records, and avoids candidate-pool "
            "expansion because recent breadth additions added old-window noise."
        ),
        "known_risks": [
            "FINRA is biweekly and delayed; it is PIT-safe but stale relative to daily price action.",
            "Borrow fee, shares available, hard-to-borrow, and short-interest-float fields are unavailable in the official CSV.",
            "RS20 and own-green are existing positive states; the only new information should come from their interaction with high days-to-cover.",
            "A positive replay scout is not production-tradable until a shared FINRA adapter and parity tests are added.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry FINRA days-to-cover top-ups without borrow/float context, event-quality labels, or forward short-squeeze attribution."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_037_finra_short_squeeze_demand_topup.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> dict[str, Any]:
    result = run()
    base.persist(result)
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
                "selected_risk_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
