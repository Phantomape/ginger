"""exp-20260609-010: volatility-relief industry laggard repair.

Replay-only alpha search. It tests one free-OHLCV relation alpha: on accepted
volatility-relief days, admit strong-industry laggards that start repairing
without promoting the existing same-day stock-leadership sleeve.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import exp_20260609_008_low_turnover_rs_consolidation as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-010"
STEM = "volatility_relief_industry_laggard_repair"
TRIAL_FAMILY = "volatility_relief_industry_laggard_repair_candidate_pool"
TRIAL_VARIANT_ID = "volatility_relief_industry_laggard_repair_top1_next_open_10d_v1"
CHANGED_VARIABLE = "volatility_relief_industry_laggard_repair_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import industry_relative_laggard_repair_paper_sleeve as laggard  # noqa: E402
import volatility_relief_stock_leadership_paper_sleeve as vol_relief  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 15

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

LAGGARD_CONFIG = {
    **laggard.DEFAULT_CONFIG,
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": BASE_NOTIONAL_USD,
    "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
    "hold_days": HOLD_DAYS,
    "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "generic_volatility_beta",
        "window_regression",
        "drawdown_drift",
        "accepted_volatility_relief_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Accepted volatility-relief leadership proves the market-state edge, "
        "and accepted industry laggard repair proves relation/catch-up can "
        "work; risk is that combining them thins sample or just relabels the "
        "accepted leader beta."
    ),
    "recorded_at": "2026-06-09T09:08:23+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same accepted "
        "VIXY/SPY/QQQ volatility-relief state, industry laggard repair "
        "candidate rows, same-ticker core-overlap exclusion, next-open paper "
        "entry, 10-trading-day exit, costs, cooldown, accepted-volatility-"
        "relief comparator, and concentration controls in both historical "
        "replay and daily production before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

ACCEPTED_VOL_RELIEF_COMPARATOR = {
    "experiment_id": "exp-20260607-019",
    "decision": "accepted_volatility_relief_stock_leadership_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.5732,
    "total_pnl_delta_sum": 11934.79,
    "target_trade_count": 88,
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _volatility_relief_contexts(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, Any]]:
    relief_snapshot = vol_relief.leader._normalise_ohlcv_by_ticker(snapshot)
    indices = {
        ticker: vol_relief.leader._row_index(rows)
        for ticker, rows in relief_snapshot.items()
    }
    relief_dates: list[str] = []
    context_by_date: dict[str, dict[str, Any]] = {}
    failed_reasons: dict[str, int] = {}
    scan = {
        "scanned_trading_days": len(dates),
        "volatility_relief_days": 0,
        "volatility_relief_missing_context_days": 0,
        "volatility_relief_non_relief_days": 0,
        "volatility_relief_failed_reasons": failed_reasons,
        "max_vixy_relief_return": vol_relief.MAX_VIXY_RELIEF_RETURN,
        "max_vixy_close_location": vol_relief.MAX_VIXY_CLOSE_LOCATION,
        "min_spy_relief_return": vol_relief.MIN_SPY_RELIEF_RETURN,
        "min_qqq_relief_return": vol_relief.MIN_QQQ_RELIEF_RETURN,
        "min_spy_close_location": vol_relief.MIN_SPY_CLOSE_LOCATION,
        "min_qqq_close_location": vol_relief.MIN_QQQ_CLOSE_LOCATION,
    }
    for signal_date in dates:
        context = vol_relief._volatility_relief_context_for_day(
            rows_by_ticker=relief_snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            scan["volatility_relief_missing_context_days"] += 1
            continue
        context_by_date[signal_date] = context
        if not context.get("passed"):
            reason = str(context.get("reason") or "unknown")
            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
            scan["volatility_relief_non_relief_days"] += 1
            continue
        relief_dates.append(signal_date)
        scan["volatility_relief_days"] += 1
    return relief_dates, context_by_date, scan


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    required_context_tickers = {"VIXY", "SPY", "QQQ"}
    working_snapshot = snapshot
    missing_context_tickers = sorted(required_context_tickers.difference(snapshot))
    if missing_context_tickers:
        working_snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries).union(required_context_tickers),
        )
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(working_snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    relief_dates, context_by_date, relief_scan = _volatility_relief_contexts(
        snapshot=working_snapshot,
        dates=dates,
    )
    relief_scan["context_snapshot_extra_tickers_loaded"] = missing_context_tickers
    if not relief_dates:
        return [], [], {
            **relief_scan,
            "days_with_strong_groups": 0,
            "days_with_raw_vol_relief_laggard_candidates": 0,
            "raw_vol_relief_laggard_candidates": 0,
            "unique_candidate_tickers": 0,
            "rule_version": RULE_VERSION,
        }

    candidates, laggard_contexts, laggard_scan = (
        laggard.build_industry_relative_laggard_repair_candidate_rows(
            ohlcv_by_ticker=working_snapshot,
            dates=relief_dates,
            sector_entries=sector_entries,
            core_entries_by_date=entries_by_date,
            config=LAGGARD_CONFIG,
            require_exit_data=True,
        )
    )
    enriched: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        relief_context = context_by_date.get(signal_date, {})
        enriched.append(
            {
                **row,
                "source": "VOLATILITY_RELIEF_INDUSTRY_LAGGARD_REPAIR_PAPER",
                "rule_version": RULE_VERSION,
                "volatility_relief_rule_version": vol_relief.SOURCE_RULE_VERSION,
                "industry_laggard_repair_rule_version": laggard.SOURCE_RULE_VERSION,
                "volatility_relief_context": relief_context,
                "uses_free_ohlcv_only": True,
                "uses_llm": False,
                "trade_enabled": False,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
            }
        )
    enriched.sort(
        key=lambda row: (
            row["date"],
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("candidate_signal_relative_vs_spy") or 0.0),
            -float(row.get("candidate_industry_lag_20d") or 0.0),
            str(row.get("candidate_group_key") or ""),
            row["ticker"],
        )
    )
    context_samples: list[dict[str, Any]] = []
    for context in laggard_contexts:
        signal_date = str(context.get("date") or "")[:10]
        context_samples.append(
            {
                **context,
                "volatility_relief_context": context_by_date.get(signal_date, {}),
            }
        )
    scan = {
        **relief_scan,
        "days_with_strong_groups": laggard_scan.get("days_with_strong_groups", 0),
        "days_with_raw_vol_relief_laggard_candidates": laggard_scan.get(
            "days_with_raw_candidates",
            0,
        ),
        "raw_vol_relief_laggard_candidates": laggard_scan.get(
            "raw_candidate_rows",
            0,
        ),
        "unique_candidate_tickers": laggard_scan.get("unique_candidate_tickers", 0),
        "industry_laggard_scan": laggard_scan,
        "rule_version": RULE_VERSION,
    }
    return enriched, context_samples, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_VOL_RELIEF_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append(
            "accepted_volatility_relief_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_VOL_RELIEF_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append(
            "accepted_volatility_relief_pnl_not_beaten"
        )
    gate["accepted_volatility_relief_comparator"] = ACCEPTED_VOL_RELIEF_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_volatility_relief_industry_laggard_repair"
        if gate["passed"]
        else "rejected_volatility_relief_industry_laggard_repair_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "On accepted volatility-relief days, strong-industry laggards "
                "that begin repairing may provide second-wave replacement "
                "value distinct from same-day stock leaders."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": (
                "production_visible_free_ohlcv_volatility_relief_x_industry_laggard_relation"
            ),
            "nearby_prior_experiments": [
                "exp-20260607-019",
                "exp-20260608-022",
                "exp-20260607-008",
                "exp-20260608-008",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_volatility_relief_comparator": ACCEPTED_VOL_RELIEF_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that combining the accepted "
                "volatility-relief state with laggard repair either thins the "
                "sample too much or turns into generic relief beta without "
                "beating the accepted stock-leadership sleeve. Do not answer "
                "by sweeping VIXY/SPY/QQQ thresholds, industry lag bounds, "
                "daily slots, hold days, cooldown, or notional on these frozen "
                "windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new evidence such as forward "
                "replacement rows showing non-overlap versus the accepted "
                "volatility-relief leadership sleeve, or a production-visible "
                "relationship field not derivable from threshold retunes."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "volatility_relief_thresholds": {
                "max_vixy_relief_return": vol_relief.MAX_VIXY_RELIEF_RETURN,
                "max_vixy_close_location": vol_relief.MAX_VIXY_CLOSE_LOCATION,
                "min_spy_relief_return": vol_relief.MIN_SPY_RELIEF_RETURN,
                "min_qqq_relief_return": vol_relief.MIN_QQQ_RELIEF_RETURN,
                "min_spy_close_location": vol_relief.MIN_SPY_CLOSE_LOCATION,
                "min_qqq_close_location": vol_relief.MIN_QQQ_CLOSE_LOCATION,
            },
            "industry_laggard_repair_config": {
                key: value
                for key, value in LAGGARD_CONFIG.items()
                if key
                in {
                    "min_price",
                    "min_avg_dollar_volume_20d",
                    "group_lookback_days",
                    "recent_lookback_days",
                    "trend_lookback_days",
                    "min_industry_liquid_count",
                    "min_group_median_ret20_excess_spy",
                    "min_group_ret20_positive_fraction",
                    "min_group_median_ret5_excess_spy",
                    "min_industry_lag_20d",
                    "max_industry_lag_20d",
                    "min_candidate_ret20_excess_spy",
                    "min_candidate_ret60_excess_spy",
                    "min_candidate_ret5_excess_spy",
                    "min_signal_return",
                    "max_signal_return",
                    "min_signal_relative_vs_spy",
                    "min_close_location",
                    "min_volume_ratio_20d",
                    "max_volume_ratio_20d",
                    "max_realized_vol_20d",
                }
            },
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: accepted volatility-relief days may create "
            "a second wave in strong-industry laggards that start repairing, "
            "using only free production-visible OHLCV state and relation rows."
        ),
        "2_history_check": {
            "exp-20260607-019": (
                "Volatility-relief stock leadership was accepted with EV "
                "+0.5732 and PnL +$11,934.79; this run must beat that accepted "
                "comparator rather than retune its thresholds."
            ),
            "exp-20260608-022": (
                "Compression plus vol-relief confirmation was rejected with "
                "only four trades; this run uses industry relation/catch-up, "
                "not compression confirmation."
            ),
            "exp-20260607-008": (
                "Industry relative laggard repair was accepted; this run "
                "conditions that mechanism on the accepted volatility-relief "
                "state."
            ),
            "exp-20260608-008": (
                "Industry stable core-flow validated strong-industry context; "
                "this run is not a capital-allocation or threshold retune."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and exp-20260607-019 "
            "accepted volatility-relief comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_010_volatility_relief_industry_laggard_repair.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed vol-relief plus industry-laggard relation cleared the "
            "three-window Gate 4 and beat the accepted vol-relief comparator, "
            "suggesting second-wave relation rows add value beyond same-day "
            "leadership. It remains replay-only until shared daily parity is "
            "implemented."
            if passed
            else (
                "The fixed vol-relief plus industry-laggard relation failed "
                "Gate 4 or did not beat the accepted vol-relief comparator. "
                "The likely reason is sample thinning or generic relief beta: "
                "once next-open execution, core-overlap, cooldown, and "
                "concentration are enforced, the relation row did not add "
                "enough replacement value beyond the accepted leader sleeve."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping VIXY/SPY/QQQ relief thresholds, industry "
            "lag bounds, ret20/ret5 group thresholds, signal return, "
            "close-location, volume ratio, top-N, hold-day, cooldown, or "
            "notional on these frozen windows."
        ),
        "new_evidence_required": (
            "Next useful evidence would be forward replacement-value rows "
            "versus the accepted vol-relief stock-leadership sleeve, or an "
            "orthogonal free data edge that explains laggard catch-up within "
            "relief states without threshold retuning."
        ),
    }
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if passed else "rejected"
    payload["interpretation"] = (
        "The vol-relief industry-laggard repair source cleared Gate 4 as a "
        "replay-only/default-off lead, but no production surface was promoted. "
        "A shared parity adapter is required before use."
        if passed
        else (
            "The vol-relief industry-laggard repair source did not clear Gate "
            "4 or did not beat the accepted vol-relief comparator. Do not "
            "promote or locally retune this relation family on the frozen "
            "windows."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Relief days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {relief_days} | {candidate_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                relief_days=scan.get("volatility_relief_days", 0),
                candidate_days=scan.get(
                    "days_with_raw_vol_relief_laggard_candidates",
                    0,
                ),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Volatility-Relief Industry Laggard Repair",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_VOL_RELIEF_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_VOL_RELIEF_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_volatility_relief_comparator": ACCEPTED_VOL_RELIEF_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "volatility_relief_day_count": payload["context_scan_by_window"][
                    label
                ].get("volatility_relief_days"),
                "vol_relief_laggard_candidate_day_count": payload[
                    "context_scan_by_window"
                ][label].get("days_with_raw_vol_relief_laggard_candidates"),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
