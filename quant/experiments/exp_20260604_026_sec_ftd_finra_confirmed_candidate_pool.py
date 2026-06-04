"""exp-20260604-026: SEC FTD plus FINRA-confirmed candidate-pool scout.

This replay-only alpha search tests one free, production-visible relation:
publication-lagged SEC fails-to-deliver pressure candidates are admitted only
when the latest PIT-safe FINRA short-interest row also shows borrow pressure.

Core signals, ranking, sizing, exits, LLM/news, watchlists, shared adapters,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260604_023_sec_ftd_pressure_breakout_candidate_pool as ftd_base
from finra_iwm_paper_sleeve import (
    _finra_rows_by_ticker,
    fetch_finra_short_interest_rows,
)


EXPERIMENT_ID = "exp-20260604-026"
STEM = "sec_ftd_finra_confirmed_candidate_pool"
TRIAL_FAMILY = "sec_ftd_finra_confirmed_candidate_pool"
CHANGED_VARIABLE = "sec_ftd_candidate_requires_latest_finra_borrow_pressure_confirmation_v1"
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

MIN_FINRA_DAYS_TO_COVER = 3.0
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = ftd_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = ftd_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = ftd_base.MAX_POSITIVE_HHI

ROOT = ftd_base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_026_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FTD_ROWS_JSON = OUT_DIR / "sec_ftd_rows_summary.json"
FTD_FILES_JSON = OUT_DIR / "sec_ftd_source_files.json"
FINRA_ROWS_JSON = OUT_DIR / "finra_short_interest_rows_summary.json"
FINRA_FILES_JSON = OUT_DIR / "finra_source_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

framework = ftd_base.framework
_ORIGINAL_BUILD_PAYLOAD = ftd_base._ORIGINAL_BUILD_PAYLOAD
_FINRA_CACHE: dict[str, Any] | None = None


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


def _float(value: Any) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fetch_finra_context(universe: set[str]) -> dict[str, Any]:
    global _FINRA_CACHE
    tickers = sorted(universe.difference(framework.base.shadow.EXCLUDED_TICKERS))
    if _FINRA_CACHE is not None and _FINRA_CACHE.get("tickers") == tickers:
        return _FINRA_CACHE

    starts = [
        datetime.strptime(cfg["start"], "%Y-%m-%d").date()
        for cfg in framework.base.WINDOWS.values()
    ]
    ends = [
        datetime.strptime(cfg["end"], "%Y-%m-%d").date()
        for cfg in framework.base.WINDOWS.values()
    ]
    first = min(starts) - ftd_base.timedelta(days=75)
    last = max(ends)
    lookback_days = max(180, (last - first).days + 30)
    cache_dir = ROOT / "data" / "tmp" / EXPERIMENT_ID / "finra_source_cache"
    rows, files = fetch_finra_short_interest_rows(
        tickers=set(tickers),
        as_of=last.isoformat(),
        lookback_days=lookback_days,
        cache_dir=cache_dir,
    )
    _FINRA_CACHE = {
        "tickers": tickers,
        "rows": rows,
        "files": files,
        "rows_by_ticker": _finra_rows_by_ticker(rows),
        "lookback_days": lookback_days,
        "source": "official FINRA equity short-interest files",
    }
    return _FINRA_CACHE


def _latest_finra_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [
        row for row in rows if str(row.get("publication_date") or "") <= signal_date
    ]
    if not eligible:
        return None
    return eligible[-1]


def _finra_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_publication_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    for row in rows:
        publication = str(row.get("publication_date") or "")
        if len(publication) >= 7:
            by_publication_month[publication[:7]] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "publication_month_counts": dict(sorted(by_publication_month.items())),
        "top_ticker_row_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "note": (
            "Raw FINRA source files are fetched/cached under data/tmp; this "
            "artifact keeps only summary counts for reproducibility."
        ),
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
    finra_context = _fetch_finra_context(universe)
    ftd_rows_by_ticker = ftd_context["rows_by_ticker"]
    finra_rows_by_ticker = finra_context["rows_by_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    finra_examples: list[dict[str, Any]] = []
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

            finra = _latest_finra_row(finra_rows_by_ticker, ticker, signal_date)
            if finra is None:
                reject_counts["missing_latest_finra_row"] += 1
                continue
            days_to_cover = _float(finra.get("days_to_cover"))
            short_change_pct = _float(finra.get("short_interest_change_pct"))
            if days_to_cover is None:
                reject_counts["missing_finra_days_to_cover"] += 1
                continue
            if short_change_pct is None:
                reject_counts["missing_finra_short_interest_change_pct"] += 1
                continue
            if days_to_cover < MIN_FINRA_DAYS_TO_COVER:
                reject_counts["finra_days_to_cover_below_threshold"] += 1
                continue
            if short_change_pct <= MIN_FINRA_SHORT_INTEREST_CHANGE_PCT:
                reject_counts["finra_short_interest_change_not_positive"] += 1
                continue
            raw_pass_counts["finra_borrow_pressure_confirmed"] += 1

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
                "finra_publication_date": finra.get("publication_date"),
                "finra_settlement_date": finra.get("settlement_date"),
                "finra_days_to_cover": framework._round(days_to_cover, 6),
                "finra_short_interest_change_pct": framework._round(
                    short_change_pct,
                    6,
                ),
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
            if len(finra_examples) < 20:
                finra_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "ftd_notional_to_adv20": candidate["ftd_notional_to_adv20"],
                        "finra_days_to_cover": candidate["finra_days_to_cover"],
                        "finra_short_interest_change_pct": candidate[
                            "finra_short_interest_change_pct"
                        ],
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
        "finra_reject_counts": dict(sorted(reject_counts.items())),
        "finra_confirmed_examples": finra_examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    ftd_context = ftd_base._FTD_CACHE or {}
    finra_context = _FINRA_CACHE or {}
    framework._write_json(FTD_ROWS_JSON, ftd_base._ftd_rows_summary(ftd_context.get("rows", [])))
    framework._write_json(FTD_FILES_JSON, ftd_context.get("files", []))
    framework._write_json(FINRA_ROWS_JSON, _finra_rows_summary(finra_context.get("rows", [])))
    framework._write_json(FINRA_FILES_JSON, finra_context.get("files", []))

    passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_lead_not_promoted_requires_ftd_finra_shared_adapter"
        if passed
        else "rejected_sec_ftd_finra_confirmed_candidate_pool"
    )
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    rationale = (
        "Gate 4 passed, but FTD+FINRA remains replay-only until a shared "
        "default-off adapter implements the same PIT source policies in "
        "production and backtest."
        if passed
        else "Gate 4 failed; no production or shared policy behavior is retained."
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
                "replacement value when confirmed by latest PIT FINRA borrow "
                "pressure, combining settlement stress with borrow crowding "
                "without adding noisy tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "free_sec_settlement_plus_borrow_pressure",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260604-023",
                "exp-20260604-024",
                "exp-20260603-006",
                "exp-20260603-007",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_sec_ftd_plus_official_finra_borrow_pressure_relation",
            "interpretation": rationale,
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_gates"]),
            "prediction": {
                "success_probability": 0.21,
                "expected_ev_delta": 0.12,
                "expected_pnl_delta": 2000.0,
                "main_failure_modes": [
                    "thin_overlap",
                    "late_strong_regression",
                    "accepted_finra_comparator_underperformance",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "FTD standalone was broad and aggregate positive but "
                    "regressed late_strong; FINRA borrow-pressure has accepted "
                    "evidence, so cross-source confirmation is materially "
                    "different but may be too thin."
                ),
                "recorded_at": "2026-06-04T21:05:51+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.21 - actual_success) ** 2, 6),
            },
            "sec_ftd_source": {
                "source_page": ftd_base.SEC_FTD_PAGE,
                "row_count": len(ftd_context.get("rows", [])),
                "file_count": len(ftd_context.get("files", [])),
                "rows_artifact": framework._repo_rel(FTD_ROWS_JSON),
                "files_artifact": framework._repo_rel(FTD_FILES_JSON),
                "publication_lag_note": ftd_context.get("publication_lag_note"),
            },
            "finra_source": {
                "source": finra_context.get("source"),
                "row_count": len(finra_context.get("rows", [])),
                "file_count": len(finra_context.get("files", [])),
                "lookback_days": finra_context.get("lookback_days"),
                "rows_artifact": framework._repo_rel(FINRA_ROWS_JSON),
                "files_artifact": framework._repo_rel(FINRA_FILES_JSON),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "FTD pressure candidate must also have latest publication-date "
                "safe FINRA row with days_to_cover >= 3.0 and "
                "short_interest_change_pct > 0.0."
            ),
            "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
            "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: settlement-fail pressure should be cleaner "
            "when independent FINRA short-interest data confirms borrow crowding."
        ),
        "2_history_check": {
            "exp-20260604-023": (
                "Standalone FTD pressure was aggregate positive but failed "
                "late_strong and therefore was rejected."
            ),
            "exp-20260604-024": (
                "Form4+FTD overlap was too thin and failed raw Form4 comparator."
            ),
            "exp-20260603-006/007": (
                "FINRA borrow-pressure admission passed and was promoted as a "
                "default-off adapter; this run uses FINRA as independent "
                "confirmation, not a FINRA threshold retune."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample, drawdown, survival, "
            "and concentration guards pass; no production/backtest divergence."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.py"
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
            "finra_required_fields": [
                "publication_date",
                "days_to_cover",
                "short_interest_change_pct",
            ],
            "llm_dependency": False,
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
            "only a replay lead until the same FTD+FINRA source policies are "
            "implemented in a shared default-off adapter with parity tests."
        ),
    }
    payload["next_retry_requires"] = (
        "If rejected, do not retune nearby FTD or FINRA thresholds on the "
        "frozen windows; require forward replacement rows, a cleaner borrow-cost "
        "field, or a materially different relation."
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(FTD_ROWS_JSON),
        framework._repo_rel(FTD_FILES_JSON),
        framework._repo_rel(FINRA_ROWS_JSON),
        framework._repo_rel(FINRA_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["gate4"]["requires_parity_before_promotion"] = passed
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC FTD + FINRA Confirmed Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['baseline_expected_value_score_sum']}` -> "
        f"`{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- aggregate PnL delta: `${agg['total_pnl_delta_sum']:+,.2f}`",
        f"- target trades: `{target['total_trade_count']}`",
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
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "The tested fields are SEC FTD rows after conservative publication "
            "lag, official FINRA rows after FINRA publication-date rules, and "
            "same-day/prior OHLCV. The result is replay-only/default-off: no "
            "production entry, ranking, sizing, exit, LLM/news, watchlist, or "
            "order behavior changed.",
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
