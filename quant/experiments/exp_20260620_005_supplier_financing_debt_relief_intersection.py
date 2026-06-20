"""exp-20260620-005: supplier financing plus debt relief intersection scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose quarterly
accounts-payable DPO is extending while annual principal debt/revenue burden is
also falling. The economic idea is that supplier financing is useful only when
it accompanies balance-sheet repair, not when it is masking leverage stress.

This intentionally reuses the PIT parsers from the two rejected standalone
scouts and tests only the same-date cross-statement intersection. No production
code, shared adapter, live/default orders, ranking, sizing, exits, LLM/news
path, or watchlist behavior is changed. A positive replay would only be a lead
until a shared historical/daily helper reproduces it. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260614_020_accruals_cash_conversion_quality as base  # noqa: E402
import exp_20260616_029_principal_debt_burden_relief as debt  # noqa: E402
import exp_20260617_001_accounts_payable_dpo_extension as dpo  # noqa: E402


EXPERIMENT_ID = "exp-20260620-005"
STEM = "supplier_financing_debt_relief_intersection"
TRIAL_FAMILY = "supplier_financing_debt_relief_intersection_candidate_pool"
TRIAL_VARIANT_ID = "supplier_financing_debt_relief_intersection_top1_next_open_10d_v1"
CHANGED_VARIABLE = (
    "raw_sec_companyfacts_supplier_financing_debt_relief_intersection_candidate_source_v1"
)
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "sample_too_thin",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Standalone accounts-payable DPO extension and principal debt burden "
        "relief each showed strong late/mid evidence but failed risk or old-"
        "window guards. The new test is the same-date cross-statement "
        "intersection: supplier financing must be paired with deleveraging. "
        "The main disconfirmer is thin overlap and repeated saturation in raw "
        "Companyfacts candidate pools."
    ),
    "recorded_at": "2026-06-20T05:05:24+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_llm": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC accounts-payable/COGS facts, missing raw SEC debt "
            "or annual revenue facts, stale filings, missing CIK mapping, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until one shared default-off helper computes the same "
        "PIT accounts-payable DPO extension, principal debt/revenue burden "
        "relief, price confirmation, cooldown, next-open paper entry, 10-day "
        "exit, costs, and concentration controls in both historical replay and "
        "daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts quarterly DPO extension paired "
        "with annual principal debt/revenue burden relief may identify companies "
        "funding growth through operating supplier credit rather than balance-"
        "sheet leverage, producing next-open 10-day continuation value."
    ),
    "2_history_check": {
        "exp-20260617-001": (
            "Standalone accounts-payable DPO extension improved all windows but "
            "failed on drawdown drift. This run is not a DPO threshold sweep; it "
            "requires same-date principal debt burden relief."
        ),
        "exp-20260616-029": (
            "Standalone principal debt burden relief improved late/mid but "
            "regressed old_thin and drawdown. This run is not a debt threshold "
            "sweep; it requires operating supplier-financing quality."
        ),
        "exp-20260617-005": (
            "D&A burden relief was another raw Companyfacts relief field with "
            "old_thin/drawdown failure. This run combines two cross-statement "
            "cash/leverage fields rather than another cost-burden tag."
        ),
        "exp-20260619-005": (
            "Debt maturity cliff relief failed old_thin and concentration. This "
            "run uses filed raw debt burden plus supplier credit, not maturity "
            "bucket retuning."
        ),
        "novelty_gate": (
            "Novelty gate warned on DPO/debt Companyfacts near-neighbors. The "
            "override recorded the new evidence axis: same-date cross-statement "
            "intersection of quarterly payables DPO and annual deleveraging."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_005_supplier_financing_debt_relief_intersection.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payables_index, payables_summary = dpo._load_raw_companyfacts_index()
    debt_index, debt_summary = debt._load_raw_companyfacts_index()
    tickers = sorted(set(payables_index) & set(debt_index))
    combined = {
        ticker: {
            "payables": payables_index[ticker],
            "debt": debt_index[ticker],
        }
        for ticker in tickers
    }
    return combined, {
        "field_source": "raw_sec_companyfacts_cache_cross_statement_intersection",
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "raw_companyfacts_cache": _repo_rel(dpo.RAW_COMPANYFACTS_CACHE),
        "payables_index_tickers": len(payables_index),
        "debt_index_tickers": len(debt_index),
        "intersection_tickers": len(combined),
        "payables_summary": payables_summary,
        "debt_summary": debt_summary,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            payables_observation = dpo._payables_observation(
                ticker, signal_date, quality_index[ticker]["payables"]
            )
            if payables_observation is None:
                scan["failed_dpo_extension_gate"] += 1
                continue
            debt_observation = debt._debt_observation(
                ticker, signal_date, quality_index[ticker]["debt"]
            )
            if debt_observation is None:
                scan["failed_debt_relief_gate"] += 1
                continue
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            dpo_extension = float(payables_observation["dpo_extension_days"] or 0.0)
            cogs_growth = float(payables_observation["cogs_growth"] or 0.0)
            gross_profit_growth = payables_observation.get("gross_profit_growth")
            gross_profit_component = 0.0
            if gross_profit_growth is not None:
                gross_profit_component = max(min(float(gross_profit_growth), 0.60), -0.05)
            debt_ratio_improvement = float(
                debt_observation["debt_ratio_improvement"] or 0.0
            )
            revenue_growth = float(debt_observation["revenue_growth"] or 0.0)
            debt_growth_spread = float(
                debt_observation["debt_growth_minus_revenue_growth"] or 0.0
            )
            current_debt_ratio = float(debt_observation["current_debt_to_revenue"] or 0.0)
            current_dpo = float(payables_observation["current_dpo_days"] or 0.0)
            score = (
                0.018 * min(dpo_extension, 50.0)
                + 1.20 * min(debt_ratio_improvement, 0.45)
                + 0.16 * max(min(cogs_growth, 0.60), -0.05)
                + 0.16 * gross_profit_component
                + 0.18 * max(min(revenue_growth, 0.60), 0.0)
                + 0.10 * max(min(-debt_growth_spread, 0.50), -0.25)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.08 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(
                    max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0)
                    / 1_000_000.0
                )
                - 0.002 * max(current_dpo - 120.0, 0.0)
                - 0.025 * max(current_debt_ratio - 0.75, 0.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SUPPLIER_FINANCING_DEBT_RELIEF_INTERSECTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"payables_{k}": v for k, v in payables_observation.items()},
                    **{f"debt_{k}": v for k, v in debt_observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(
            existing["candidate_score"]
        ):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["debt_debt_ratio_improvement"] or 0.0),
            -float(row["payables_dpo_extension_days"] or 0.0),
            float(row["debt_debt_growth_minus_revenue_growth"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "payables_rule_version": dpo.RULE_VERSION,
        "debt_rule_version": debt.RULE_VERSION,
        "intersection_gate": (
            "DPO extension observation and principal debt burden relief "
            "observation must both exist for the same ticker/signal date."
        ),
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_supplier_financing_debt_relief_intersection"
        if gate["passed"]
        else "rejected_supplier_financing_debt_relief_intersection_candidate_pool"
    )
    return gate


def _configure_framework() -> None:
    base.framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.framework.HOLD_DAYS = HOLD_DAYS
    base.framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS


def _build_payload() -> dict[str, Any]:
    _configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = base.framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(base.framework.get_universe())
    sector_entries_all = base.framework._load_sector_entries()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    quality_index_summary_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.framework.WINDOWS.items():
        print(f"[{label}] core baseline and supplier-financing/debt-relief replay")
        before_result = base.framework.shadow._run_baseline(universe, cfg)
        before = base.framework.overlay_helper._metrics(before_result)
        snapshot = base._load_window_snapshot(cfg=cfg, eligible_tickers=set(universe))
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        quality_index, quality_summary = _build_quality_index([])
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_ticker_count": len(sector_entries),
            "source": _repo_rel(base.framework.WAREHOUSE),
        }
        quality_index_summary_by_window[label] = quality_summary
        candidates, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
            quality_index=quality_index,
        )
        selected_trades, filtered_candidates = base.framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = base.framework.sleeve._overlay_from_paper_trades(
            before_result, selected_trades
        )
        after = base.framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = base.framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_scan_by_window[label] = context_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = base.framework._aggregate_window_rows(window_rows)
    target_summary = base.framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    failed_reasons = gate4["failed_reasons"]
    if gate4["passed"]:
        interpretation = (
            "The supplier-financing plus debt-relief intersection cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "Rejected. The supplier-financing plus debt-relief intersection did "
            f"not clear Gate 4 (failed: {', '.join(failed_reasons) or 'none'}). "
            "The overlap did not convert two directionally positive standalone "
            "Companyfacts fields into a robust replacement-value source."
        )
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": failed_reasons,
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": gate4["passed"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": (
            "production_visible_free_sec_companyfacts_cross_statement_candidate_pool"
        ),
        "new_evidence_type": "raw_sec_companyfacts_payables_dpo_plus_debt_relief_intersection",
        "nearby_prior_experiments": [
            "exp-20260617-001",
            "exp-20260616-029",
            "exp-20260617-005",
            "exp-20260619-005",
        ],
        "prior_trial_count": 2,
        "multiple_testing_risk_bucket": "high",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": base.framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(base.framework.WAREHOUSE),
            "companyfacts_source": _repo_rel(dpo.RAW_COMPANYFACTS_CACHE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "AccountsPayableCurrent / AccountsPayableTradeCurrent are read "
                "as raw SEC Companyfacts balance-sheet INSTANT facts and matched "
                "to quarterly COGS to compute DPO extension. Gross debt and "
                "annual revenue are read from raw SEC Companyfacts and matched "
                "by fiscal-year end to compute debt/revenue burden relief. Both "
                "observations must be filed on or before the signal date for the "
                "same ticker. Price confirmation uses signal-date OHLCV only. "
                "Paper entry is next available open with existing entry slippage; "
                "exit is the close 10 trading days after the signal with target-"
                "side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "payables_rule_version": dpo.RULE_VERSION,
            "debt_rule_version": debt.RULE_VERSION,
            "min_price": base.MIN_PRICE,
            "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
            "min_signal_return": base.MIN_SIGNAL_RETURN,
            "max_signal_return": base.MAX_SIGNAL_RETURN,
            "min_close_location": base.MIN_CLOSE_LOCATION,
            "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "raw SEC Companyfacts AccountsPayableCurrent / AccountsPayableTradeCurrent",
                "raw SEC Companyfacts quarterly COGS",
                "raw SEC Companyfacts gross debt instant facts",
                "raw SEC Companyfacts annual revenue facts",
                "raw SEC Companyfacts filed date and period end",
                "warehouse ticker_universe CIK mapping",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV for relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate source "
                "is additive default-off paper, so core signals generated/survived "
                "are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "accepted_compression_comparator": base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": base.DISTRIBUTION_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "quality_index_summary_by_window": quality_index_summary_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(failed_reasons),
        "next_evidence_needed": (
            "A retry needs materially different PIT supplier/debt evidence such "
            "as supplier concentration, payment-term disclosures, covenant/"
            "refinancing terms, or closed forward replacement-value rows. Do not "
            "sweep DPO thresholds, debt/revenue thresholds, fact freshness, "
            "price guards, top-N, hold, cooldown, or notional on these frozen "
            "windows."
        ),
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown drift {:+.4f}; {} paper trades.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    target_summary["total_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping DPO extension, debt/revenue relief, "
                "COGS/revenue floors, fact freshness, RS/close/volume/vol guards, "
                "top-N, hold days, cooldown, or notional on these frozen windows."
            ),
            "new_evidence_required": (
                "Need supplier/payment-term provenance, covenant/refinancing "
                "context, or closed forward replacement-value rows before "
                "revisiting this Companyfacts cross-statement family."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Supplier Financing Debt Relief Intersection",
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
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
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
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": base.DISTRIBUTION_COMPARATOR,
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get(
                    "eligible_quality_tickers"
                ),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
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
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
