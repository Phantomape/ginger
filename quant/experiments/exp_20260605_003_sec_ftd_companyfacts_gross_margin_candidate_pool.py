"""exp-20260605-003: SEC FTD plus Companyfacts gross-margin candidate-pool scout.

Replay-only alpha search. It tests whether official SEC FTD pressure candidates
are cleaner when the ticker also has filed-date SEC Companyfacts gross-margin
quality. Core signals, shared ranking, sizing, exits, LLM/news, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260604_023_sec_ftd_pressure_breakout_candidate_pool as ftd_base


ROOT = ftd_base.ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "quant" / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant" / "experiments"))

from exp_20260601_021_companyfacts_gross_margin_rs_candidate_pool import (  # noqa: E402
    GrossMarginIndex,
    MIN_GROSS_MARGIN,
)


EXPERIMENT_ID = "exp-20260605-003"
STEM = "sec_ftd_companyfacts_gross_margin_candidate_pool"
TRIAL_FAMILY = "sec_ftd_companyfacts_quality_confirmed_candidate_pool"
CHANGED_VARIABLE = "sec_ftd_candidate_requires_companyfacts_gross_margin_confirmation_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = ftd_base.BASE_NOTIONAL_USD
HOLD_DAYS = ftd_base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = ftd_base.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = ftd_base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = ftd_base.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = ftd_base.MIN_VOLUME_RATIO_20
MIN_CLOSE_LOCATION = ftd_base.MIN_CLOSE_LOCATION
MIN_RET20_EXCESS_SPY = ftd_base.MIN_RET20_EXCESS_SPY
MIN_FTD_SHARES = ftd_base.MIN_FTD_SHARES
MIN_FTD_NOTIONAL = ftd_base.MIN_FTD_NOTIONAL
MIN_FTD_NOTIONAL_TO_ADV20 = ftd_base.MIN_FTD_NOTIONAL_TO_ADV20
MAX_FTD_PUBLICATION_AGE_DAYS = ftd_base.MAX_FTD_PUBLICATION_AGE_DAYS

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = ftd_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = ftd_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = ftd_base.MAX_POSITIVE_HHI

ACCEPTED_FTD_FINRA_JSON = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260604-026"
    / "exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.json"
)

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_003_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FTD_ROWS_JSON = OUT_DIR / "sec_ftd_rows_summary.json"
FTD_FILES_JSON = OUT_DIR / "sec_ftd_source_files.json"
COMPANYFACTS_ROWS_JSON = OUT_DIR / "companyfacts_gross_margin_rows_summary.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

framework = ftd_base.framework
_ORIGINAL_BUILD_PAYLOAD = ftd_base._ORIGINAL_BUILD_PAYLOAD
_GROSS_MARGIN_INDEX: GrossMarginIndex | None = None


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    framework.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    framework.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    framework.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_JSON = BEFORE_JSON
    framework.AFTER_JSON = AFTER_JSON
    framework.LOG_JSON = LOG_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.CARD_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._artifact = _artifact
    framework._build_payload = _build_payload


def _gross_margin_index(universe: set[str]) -> GrossMarginIndex:
    global _GROSS_MARGIN_INDEX
    if _GROSS_MARGIN_INDEX is None:
        _GROSS_MARGIN_INDEX = GrossMarginIndex(tickers=universe)
    return _GROSS_MARGIN_INDEX


def _gross_margin_rows_summary(index: GrossMarginIndex) -> dict[str, Any]:
    by_status: Counter[str] = Counter()
    tickers_by_field_count: Counter[int] = Counter()
    for ticker, field_map in index.by_ticker.items():
        if not ticker:
            continue
        field_count = sum(1 for rows in field_map.values() if rows)
        tickers_by_field_count[field_count] += 1
        if field_map.get("revenue") and (
            field_map.get("gross_profit") or field_map.get("cost_of_revenue")
        ):
            by_status["margin_computable_candidate"] += 1
        elif field_map.get("revenue"):
            by_status["revenue_only"] += 1
        else:
            by_status["missing_revenue"] += 1
    return {
        "source": "data/non_ohlcv/sec_companyfacts_selected_*.jsonl",
        "known_at": "SEC Companyfacts filed date <= signal date",
        "min_gross_margin": MIN_GROSS_MARGIN,
        "ticker_count": len(index.by_ticker),
        "status_counts": dict(sorted(by_status.items())),
        "tickers_by_nonempty_field_count": dict(sorted(tickers_by_field_count.items())),
        "fields": ["revenue", "gross_profit", "cost_of_revenue"],
    }


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy = ftd_base._prepared_frame(frames["SPY"]) if "SPY" in frames else None
    if spy is None:
        raise RuntimeError("SPY is required for ret20 excess control")

    universe = {ticker.upper() for ticker in frames}
    ftd_context = ftd_base._fetch_ftd_context(universe)
    margin_index = _gross_margin_index(universe)
    ftd_rows_by_ticker = ftd_context["rows_by_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    margin_status_counts: Counter[str] = Counter()
    margin_examples: list[dict[str, Any]] = []
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    spy_closes = [float(value) for value in spy["Close"].tolist()]

    for ticker, frame in frames.items():
        ticker = ticker.upper()
        if ticker in framework.base.shadow.EXCLUDED_TICKERS or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        fr = ftd_base._prepared_frame(frame)
        closes = [float(value) for value in fr["Close"].tolist()]
        pos_by_date = {idx: pos for pos, idx in enumerate(fr.index)}
        for asof in fr.loc[start:end].index:
            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            signal_date = str(asof.date())
            ftd = ftd_base._latest_ftd_row(ftd_rows_by_ticker, ticker, signal_date)
            if ftd is None:
                continue
            publication_age = (
                datetime.strptime(signal_date, "%Y-%m-%d").date()
                - datetime.strptime(str(ftd["publication_date"]), "%Y-%m-%d").date()
            ).days
            if publication_age < 0 or publication_age > MAX_FTD_PUBLICATION_AGE_DAYS:
                continue
            raw_pass_counts["ftd_publication_lag_passed"] += 1

            row = fr.loc[asof]
            spy_pos = int(spy.index.get_loc(asof))
            ret20 = framework._ret(closes, pos, 20)
            spy_ret20 = framework._ret(spy_closes, spy_pos, 20)
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "ret20_excess_spy": (
                    ret20 - spy_ret20
                    if ret20 is not None and spy_ret20 is not None
                    else None
                ),
                "ftd_shares": float(ftd["ftd_shares"]),
                "ftd_notional": float(ftd["ftd_notional"]),
            }
            if any(value is None or not math.isfinite(value) for value in values.values()):
                continue
            raw_pass_counts["fields_non_null"] += 1
            if values["close"] < MIN_PRICE:
                continue
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if bool(row.get("breakout_20")) is not True:
                continue
            raw_pass_counts["breakout_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                continue
            if values["close_location"] < MIN_CLOSE_LOCATION:
                continue
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                continue
            raw_pass_counts["price_action_passed"] += 1
            if values["ftd_shares"] < MIN_FTD_SHARES:
                continue
            if values["ftd_notional"] < MIN_FTD_NOTIONAL:
                continue
            ftd_to_adv20 = values["ftd_notional"] / values["avg_dollar_volume_20"]
            if ftd_to_adv20 < MIN_FTD_NOTIONAL_TO_ADV20:
                continue
            raw_pass_counts["ftd_pressure_passed"] += 1

            margin_context = margin_index.context(ticker, signal_date)
            margin_status = str(margin_context.get("gross_margin_status") or "unknown")
            margin_status_counts[margin_status] += 1
            if margin_context.get("gross_margin_pass_v1") is not True:
                reject_counts[f"companyfacts_{margin_status}"] += 1
                continue
            raw_pass_counts["companyfacts_gross_margin_confirmed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            score = (
                math.log1p(values["ftd_notional"]) * 0.45
                + min(ftd_to_adv20, 0.08) * 100.0
                + values["ret20_excess_spy"] * 2.0
                + min(values["volume_ratio_20"], 4.0) * 0.25
                + values["close_location"]
            )
            candidate = {
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "window": label,
                "score": framework._round(score, 6),
                "ftd_publication_date": ftd["publication_date"],
                "ftd_settlement_date": ftd["settlement_date"],
                "ftd_publication_age_days": publication_age,
                "ftd_shares": int(values["ftd_shares"]),
                "ftd_notional": framework._round(values["ftd_notional"], 2),
                "ftd_notional_to_adv20": framework._round(ftd_to_adv20, 6),
                "gross_margin": margin_context.get("gross_margin"),
                "gross_margin_status": margin_context.get("gross_margin_status"),
                "gross_margin_source": margin_context.get("gross_margin_source"),
                "gross_margin_threshold_min": MIN_GROSS_MARGIN,
                "revenue_filed": margin_context.get("revenue_filed"),
                "revenue_period_end": margin_context.get("revenue_period_end"),
                "gross_profit_filed": margin_context.get("gross_profit_filed"),
                "cost_of_revenue_filed": margin_context.get("cost_of_revenue_filed"),
                "companyfacts_known_at": margin_context.get("known_at"),
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "same_day_core_entry_count": len(same_day_core),
                "same_ticker_core_overlap": False,
                "source_page": ftd_base.SEC_FTD_PAGE,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
            if len(margin_examples) < 20:
                margin_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "ftd_notional_to_adv20": candidate["ftd_notional_to_adv20"],
                        "gross_margin": candidate["gross_margin"],
                        "gross_margin_source": candidate["gross_margin_source"],
                        "revenue_filed": candidate["revenue_filed"],
                    }
                )
            candidates_by_date.setdefault(signal_date, []).append(candidate)

    selected: list[dict[str, Any]] = []
    raw_candidate_count = 0
    for signal_date, rows in sorted(candidates_by_date.items()):
        raw_candidate_count += len(rows)
        rows.sort(
            key=lambda item: (
                -float(item["score"]),
                -float(item["ftd_notional_to_adv20"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "companyfacts_gross_margin_reject_counts": dict(sorted(reject_counts.items())),
        "companyfacts_gross_margin_status_counts": dict(sorted(margin_status_counts.items())),
        "companyfacts_gross_margin_confirmed_examples": margin_examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _load_accepted_ftd_finra_payload() -> dict[str, Any] | None:
    if not ACCEPTED_FTD_FINRA_JSON.exists():
        return None
    return json.loads(ACCEPTED_FTD_FINRA_JSON.read_text(encoding="utf-8"))


def _accepted_comparator(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    comparator = _load_accepted_ftd_finra_payload()
    if comparator is None:
        return {
            "comparator_experiment_id": "exp-20260604-026",
            "comparator_artifact": framework._repo_rel(ACCEPTED_FTD_FINRA_JSON),
            "available": False,
        }, ["accepted_ftd_finra_comparator_missing"]

    ours_agg = payload["aggregate"]
    comp_agg = comparator["aggregate"]
    aggregate = {
        "ours_after_ev": ours_agg["after_expected_value_score_sum"],
        "accepted_ftd_finra_after_ev": comp_agg["after_expected_value_score_sum"],
        "after_ev_delta_vs_accepted_ftd_finra": framework._round(
            ours_agg["after_expected_value_score_sum"]
            - comp_agg["after_expected_value_score_sum"],
            6,
        ),
        "ours_after_pnl": ours_agg["after_total_pnl_sum"],
        "accepted_ftd_finra_after_pnl": comp_agg["after_total_pnl_sum"],
        "after_pnl_delta_vs_accepted_ftd_finra": framework._round(
            ours_agg["after_total_pnl_sum"] - comp_agg["after_total_pnl_sum"],
            2,
        ),
        "ours_target_trades": payload["target_trade_summary"]["total_trade_count"],
        "accepted_ftd_finra_target_trades": comparator["target_trade_summary"][
            "total_trade_count"
        ],
    }

    windows: dict[str, dict[str, Any]] = {}
    for label, row in payload["window_results"].items():
        comp_row = comparator["window_results"].get(label)
        if comp_row is None:
            continue
        windows[label] = {
            "ours_after_ev": row["after"]["expected_value_score"],
            "accepted_ftd_finra_after_ev": comp_row["after"]["expected_value_score"],
            "after_ev_delta_vs_accepted_ftd_finra": framework._round(
                row["after"]["expected_value_score"]
                - comp_row["after"]["expected_value_score"],
                6,
            ),
            "ours_after_pnl": row["after"]["total_pnl"],
            "accepted_ftd_finra_after_pnl": comp_row["after"]["total_pnl"],
            "after_pnl_delta_vs_accepted_ftd_finra": framework._round(
                row["after"]["total_pnl"] - comp_row["after"]["total_pnl"],
                2,
            ),
            "ours_target_trades": row["target_trade_count"],
            "accepted_ftd_finra_target_trades": comp_row["target_trade_count"],
        }

    failed: list[str] = []
    if aggregate["after_ev_delta_vs_accepted_ftd_finra"] <= 0:
        failed.append("accepted_ftd_finra_aggregate_ev_not_beaten")
    if aggregate["after_pnl_delta_vs_accepted_ftd_finra"] <= 0:
        failed.append("accepted_ftd_finra_aggregate_pnl_not_beaten")
    if any(row["after_ev_delta_vs_accepted_ftd_finra"] < 0 for row in windows.values()):
        failed.append("accepted_ftd_finra_window_ev_regression")
    if any(row["after_pnl_delta_vs_accepted_ftd_finra"] < 0 for row in windows.values()):
        failed.append("accepted_ftd_finra_window_pnl_regression")

    return {
        "comparator_experiment_id": "exp-20260604-026",
        "comparator_artifact": framework._repo_rel(ACCEPTED_FTD_FINRA_JSON),
        "available": True,
        "aggregate": aggregate,
        "windows": windows,
        "acceptance_rule": (
            "This adjacent FTD route must beat accepted FTD+FINRA aggregate "
            "after EV and PnL, with no per-window EV/PnL regression versus that "
            "accepted comparator."
        ),
    }, failed


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    ftd_context = ftd_base._FTD_CACHE or {}
    margin_index = _GROSS_MARGIN_INDEX
    framework._write_json(FTD_ROWS_JSON, ftd_base._ftd_rows_summary(ftd_context.get("rows", [])))
    framework._write_json(FTD_FILES_JSON, ftd_context.get("files", []))
    if margin_index is not None:
        framework._write_json(COMPANYFACTS_ROWS_JSON, _gross_margin_rows_summary(margin_index))

    comparator, comparator_failed = _accepted_comparator(payload)
    base_failed = list(payload["gate4"]["failed_gates"])
    failed = sorted(set(base_failed + comparator_failed))
    passed = bool(payload["gate4"]["passed"]) and not comparator_failed
    decision = (
        "positive_replay_lead_not_promoted_requires_ftd_companyfacts_shared_adapter"
        if passed
        else "rejected_sec_ftd_companyfacts_gross_margin_candidate_pool"
    )
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    rationale = (
        "Gate 4 and accepted FTD+FINRA comparator gates passed, but this route "
        "remains replay-only until a shared default-off adapter proves the same "
        "FTD and Companyfacts PIT policies in production and backtest."
        if passed
        else "Gate 4 or the accepted FTD+FINRA comparator failed; no production or shared policy behavior is retained."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "Publication-lagged SEC FTD pressure candidates may have cleaner "
                "replacement value when confirmed by filed-date SEC Companyfacts "
                "gross-margin quality, using a different free source relation "
                "than FINRA borrow pressure."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "free_sec_ftd_plus_companyfacts_quality",
            "prior_trial_count": 5,
            "nearby_prior_experiments": [
                "exp-20260604-023",
                "exp-20260604-026",
                "exp-20260604-027",
                "exp-20260601-021",
                "exp-20260601-026",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_sec_ftd_plus_filed_date_companyfacts_quality_relation",
            "interpretation": rationale,
            "rejection_reason": None if passed else "; ".join(failed),
            "prediction": {
                "success_probability": 0.18,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "accepted_ftd_finra_comparator_underperformance",
                    "late_strong_regression",
                    "thin_or_concentrated_overlap",
                ],
                "confidence_reason": (
                    "Standalone FTD was broad but failed one window; FTD+FINRA "
                    "passed and is the valid comparator. Gross margin is a "
                    "production-visible accepted Companyfacts quality field, so "
                    "this tests a distinct source relation but likely needs "
                    "strong cross-window replacement value."
                ),
                "recorded_at": "2026-06-05T02:06:49+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.18 - actual_success) ** 2, 6),
            },
            "accepted_ftd_finra_comparator": comparator,
            "sec_ftd_source": {
                "source_page": ftd_base.SEC_FTD_PAGE,
                "row_count": len(ftd_context.get("rows", [])),
                "file_count": len(ftd_context.get("files", [])),
                "rows_artifact": framework._repo_rel(FTD_ROWS_JSON),
                "files_artifact": framework._repo_rel(FTD_FILES_JSON),
                "publication_lag_note": ftd_context.get("publication_lag_note"),
            },
            "companyfacts_source": {
                "source": "data/non_ohlcv/sec_companyfacts_selected_*.jsonl",
                "known_at": "SEC Companyfacts filed date <= signal date",
                "min_gross_margin": MIN_GROSS_MARGIN,
                "summary_artifact": framework._repo_rel(COMPANYFACTS_ROWS_JSON),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "FTD pressure candidate must also have filed-date safe "
                "SEC Companyfacts gross_margin >= 0.40."
            ),
            "min_gross_margin": MIN_GROSS_MARGIN,
            "accepted_comparator_experiment_id": "exp-20260604-026",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: settlement-fail pressure should be cleaner "
            "when independent SEC Companyfacts gross-margin quality confirms "
            "fundamental durability."
        ),
        "2_history_check": {
            "exp-20260604-023": (
                "Standalone FTD pressure was aggregate positive but failed "
                "late_strong and therefore was rejected."
            ),
            "exp-20260604-026/027": (
                "FTD+FINRA confirmation passed and was promoted default-off; "
                "this run uses that accepted route as the comparator."
            ),
            "exp-20260601-021/026": (
                "Companyfacts gross-margin quality already has a PIT filed-date "
                "implementation and shared default-off adapter evidence."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; core Gate 4 positive "
            "aggregate EV/PnL, no EV/PnL-regressed window, sample/drawdown/"
            "survival/concentration guards pass, and the accepted FTD+FINRA "
            "aggregate after EV/PnL is beaten with no per-window comparator "
            "regression."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260605_003_sec_ftd_companyfacts_gross_margin_candidate_pool.py"
        ),
    }
    payload["gate2"].update(
        {
            "minimum_open_position_fields_checked": ["entry_date", "target_price"],
            "ftd_required_fields": [
                "ftd_publication_date",
                "ftd_shares",
                "ftd_notional",
            ],
            "companyfacts_required_fields": [
                "filed",
                "revenue",
                "gross_profit_or_cost_of_revenue",
                "gross_margin",
            ],
            "llm_dependency": False,
        }
    )
    payload["gate4"].update(
        {
            "passed": passed,
            "decision": decision,
            "rationale": rationale,
            "failed_gates": failed,
            "accepted_ftd_finra_comparator_failed_gates": comparator_failed,
            "requires_parity_before_promotion": passed,
        }
    )
    payload["production_impact"].update(
        {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_data_fetch_changed": False,
            "requires_shared_adapter_before_promotion": passed,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "This runner changes no production path. A positive result would be "
            "only a replay lead until the same FTD publication-lag and "
            "Companyfacts filed-date policies are implemented in a shared "
            "default-off adapter with parity tests."
        ),
    }
    payload["next_retry_requires"] = (
        "If rejected, do not retune nearby FTD or gross-margin thresholds on the "
        "frozen windows; require forward replacement rows, a materially different "
        "free data relation, or a stronger candidate-pool expansion source."
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(FTD_ROWS_JSON),
        framework._repo_rel(FTD_FILES_JSON),
        framework._repo_rel(COMPANYFACTS_ROWS_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    comparator = payload.get("accepted_ftd_finra_comparator", {})
    comp_agg = comparator.get("aggregate", {})
    lines = [
        f"# {EXPERIMENT_ID}: SEC FTD + Companyfacts Gross-Margin Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['baseline_expected_value_score_sum']}` -> "
        f"`{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- aggregate PnL delta: `${agg['total_pnl_delta_sum']:+,.2f}`",
        f"- target trades: `{target['total_trade_count']}`",
        f"- accepted FTD+FINRA after EV delta: "
        f"`{comp_agg.get('after_ev_delta_vs_accepted_ftd_finra')}`",
        f"- accepted FTD+FINRA after PnL delta: "
        f"`${comp_agg.get('after_pnl_delta_vs_accepted_ftd_finra')}`",
        f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    if comparator.get("available"):
        lines.extend(
            [
                "",
                "## Accepted FTD+FINRA Comparator",
                "",
                "| window | ours after EV | accepted after EV | EV delta | ours after PnL | accepted after PnL | PnL delta |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for label, row in comparator.get("windows", {}).items():
            lines.append(
                f"| {label} | {row['ours_after_ev']:.4f} | "
                f"{row['accepted_ftd_finra_after_ev']:.4f} | "
                f"{row['after_ev_delta_vs_accepted_ftd_finra']:+.4f} | "
                f"${row['ours_after_pnl']:,.2f} | "
                f"${row['accepted_ftd_finra_after_pnl']:,.2f} | "
                f"${row['after_pnl_delta_vs_accepted_ftd_finra']:+,.2f} |"
            )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "The tested fields are SEC FTD rows after conservative publication "
            "lag, SEC Companyfacts rows after filed-date visibility, and same-day/"
            "prior OHLCV. The result is replay-only/default-off: no production "
            "entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior "
            "changed.",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_framework()
    return framework.run(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "accepted_ftd_finra_comparator": payload["accepted_ftd_finra_comparator"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
