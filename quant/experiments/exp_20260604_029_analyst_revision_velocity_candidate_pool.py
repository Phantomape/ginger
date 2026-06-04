"""exp-20260604-029: analyst revision velocity candidate-pool scout.

This replay-only alpha search tests one underdeveloped free-data lane:
20-trading-day EPS estimate revision velocity from daily earnings snapshots,
combined with fixed liquid breakout confirmation.

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


EXPERIMENT_ID = "exp-20260604-029"
STEM = "analyst_revision_velocity_candidate_pool"
TRIAL_FAMILY = "analyst_revision_velocity_candidate_pool"
CHANGED_VARIABLE = "earnings_snapshot_eps_estimate_revision_velocity_20d_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = ftd_base.BASE_NOTIONAL_USD
HOLD_DAYS = ftd_base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = ftd_base.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = ftd_base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = ftd_base.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = ftd_base.MIN_VOLUME_RATIO_20
MIN_CLOSE_LOCATION = ftd_base.MIN_CLOSE_LOCATION
MIN_RET20_EXCESS_SPY = ftd_base.MIN_RET20_EXCESS_SPY

REVISION_LOOKBACK_TRADING_DAYS = 20
MIN_EPS_ESTIMATE_REVISION_20D_PCT = 0.03
MIN_DAYS_TO_EARNINGS = 7
MAX_DAYS_TO_EARNINGS = 60

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = ftd_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = ftd_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = ftd_base.MAX_POSITIVE_HHI

ROOT = ftd_base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_029_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
REVISION_ROWS_JSON = OUT_DIR / "earnings_revision_rows_summary.json"
REVISION_FILES_JSON = OUT_DIR / "earnings_revision_snapshot_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

SNAPSHOT_DIR = ROOT / "data" / "daily" / "snapshots" / "earnings"
LEGACY_SNAPSHOT_DIR = ROOT / "data"

framework = ftd_base.framework
_ORIGINAL_BUILD_PAYLOAD = ftd_base._ORIGINAL_BUILD_PAYLOAD
_REVISION_CACHE: dict[str, Any] | None = None


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


def _signal_dates(frames: dict[str, pd.DataFrame]) -> list[str]:
    spy = frames.get("SPY")
    if spy is None:
        raise RuntimeError("SPY is required for canonical trading dates")
    dates: set[str] = set()
    for cfg in framework.base.WINDOWS.values():
        start = pd.Timestamp(cfg["start"])
        end = pd.Timestamp(cfg["end"])
        for asof in spy.loc[start:end].index:
            dates.add(str(asof.date()))
    return sorted(dates)


def _date_tag(iso_date: str) -> str:
    return iso_date.replace("-", "")


def _snapshot_path(iso_date: str) -> Path | None:
    tag = _date_tag(iso_date)
    organized = SNAPSHOT_DIR / f"earnings_snapshot_{tag}.json"
    if organized.exists():
        return organized
    legacy = LEGACY_SNAPSHOT_DIR / f"earnings_snapshot_{tag}.json"
    if legacy.exists():
        return legacy
    return None


def _load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload.get("earnings") or {}


def _load_revision_context(
    universe: set[str],
    frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    global _REVISION_CACHE
    tickers = sorted(
        universe.difference(framework.base.shadow.EXCLUDED_TICKERS).difference(
            {"SPY", "QQQ", "IWM"}
        )
    )
    signal_dates = _signal_dates(frames)
    cache_key = {"tickers": tickers, "signal_dates": signal_dates}
    if _REVISION_CACHE is not None and _REVISION_CACHE.get("cache_key") == cache_key:
        return _REVISION_CACHE

    all_snapshot_paths = sorted(SNAPSHOT_DIR.glob("earnings_snapshot_*.json"))
    all_dates = [
        f"{path.stem[-8:][:4]}-{path.stem[-8:][4:6]}-{path.stem[-8:][6:]}"
        for path in all_snapshot_paths
    ]
    path_by_date = dict(zip(all_dates, all_snapshot_paths))
    snapshot_by_date: dict[str, dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    rows_by_date_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    ticker_set = set(tickers)
    signal_date_set = set(signal_dates)

    for signal_date in signal_dates:
        if signal_date not in path_by_date:
            fallback = _snapshot_path(signal_date)
            if fallback is not None:
                path_by_date[signal_date] = fallback
                all_dates.append(signal_date)
            else:
                files.append(
                    {
                        "date": signal_date,
                        "status": "missing_signal_snapshot",
                        "matched_revision_rows": 0,
                    }
                )
    all_dates = sorted(set(all_dates))
    date_pos = {date: pos for pos, date in enumerate(all_dates)}

    for signal_date in signal_dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < REVISION_LOOKBACK_TRADING_DAYS:
            files.append(
                {
                    "date": signal_date,
                    "status": "missing_prior_snapshot_window",
                    "matched_revision_rows": 0,
                }
            )
            continue
        prior_date = all_dates[pos - REVISION_LOOKBACK_TRADING_DAYS]
        signal_path = path_by_date.get(signal_date) or _snapshot_path(signal_date)
        prior_path = path_by_date.get(prior_date) or _snapshot_path(prior_date)
        if signal_path is None or prior_path is None:
            files.append(
                {
                    "date": signal_date,
                    "prior_date": prior_date,
                    "status": "missing_snapshot_file",
                    "matched_revision_rows": 0,
                }
            )
            continue
        current = snapshot_by_date.setdefault(signal_date, _load_snapshot(signal_path))
        prior = snapshot_by_date.setdefault(prior_date, _load_snapshot(prior_path))
        valid_rows = 0
        qualified_rows = 0
        for ticker, current_row in current.items():
            ticker = str(ticker).upper()
            if ticker not in ticker_set:
                continue
            prior_row = prior.get(ticker)
            if not prior_row:
                continue
            current_estimate = _float(current_row.get("eps_estimate"))
            prior_estimate = _float(prior_row.get("eps_estimate"))
            days_to_earnings = _float(current_row.get("days_to_earnings"))
            if (
                current_estimate is None
                or prior_estimate is None
                or prior_estimate == 0
                or days_to_earnings is None
            ):
                continue
            revision = (current_estimate - prior_estimate) / abs(prior_estimate)
            if not math.isfinite(revision):
                continue
            valid_rows += 1
            avg_surprise = _float(current_row.get("avg_historical_surprise_pct"))
            surprise_history = current_row.get("historical_surprise_pct") or []
            positive_surprises = sum(
                1 for value in surprise_history if (_float(value) or 0.0) > 0.0
            )
            row = {
                "ticker": ticker,
                "signal_date": signal_date,
                "current_snapshot": framework._repo_rel(signal_path),
                "prior_snapshot": framework._repo_rel(prior_path),
                "prior_snapshot_date": prior_date,
                "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
                "eps_estimate_current": framework._round(current_estimate, 6),
                "eps_estimate_prior": framework._round(prior_estimate, 6),
                "eps_estimate_revision_20d_pct": framework._round(revision, 6),
                "days_to_earnings": framework._round(days_to_earnings, 2),
                "avg_historical_surprise_pct": framework._round(avg_surprise, 6),
                "positive_surprise_count": positive_surprises,
                "surprise_history_count": len(surprise_history),
                "source_caveat": (
                    "Daily snapshots are replayable, but historical EPS "
                    "estimate data should be treated as proxy-grade until a "
                    "production PIT vendor/provenance adapter is added."
                ),
            }
            rows.append(row)
            rows_by_date_ticker.setdefault(signal_date, {})[ticker] = row
            if (
                revision >= MIN_EPS_ESTIMATE_REVISION_20D_PCT
                and MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS
            ):
                qualified_rows += 1
        if signal_date in signal_date_set:
            files.append(
                {
                    "date": signal_date,
                    "prior_date": prior_date,
                    "status": "ok",
                    "snapshot_path": framework._repo_rel(signal_path),
                    "prior_snapshot_path": framework._repo_rel(prior_path),
                    "valid_revision_rows": valid_rows,
                    "matched_revision_rows": qualified_rows,
                }
            )

    _REVISION_CACHE = {
        "cache_key": cache_key,
        "rows": rows,
        "files": files,
        "rows_by_date_ticker": rows_by_date_ticker,
        "source": "daily earnings snapshots",
        "source_caveat": (
            "Historical snapshots are replayable but EPS estimate provenance is "
            "proxy-grade; positive results must not be promoted before shared "
            "PIT revision-source parity is implemented."
        ),
    }
    return _REVISION_CACHE


def _revision_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    qualified_by_month: Counter[str] = Counter()
    for row in rows:
        signal_date = str(row.get("signal_date") or "")
        month = signal_date[:7]
        if month:
            by_month[month] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
        revision = _float(row.get("eps_estimate_revision_20d_pct"))
        days_to_earnings = _float(row.get("days_to_earnings"))
        if (
            revision is not None
            and days_to_earnings is not None
            and revision >= MIN_EPS_ESTIMATE_REVISION_20D_PCT
            and MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS
        ):
            qualified_by_month[month] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "revision_month_counts": dict(sorted(by_month.items())),
        "qualified_revision_month_counts": dict(sorted(qualified_by_month.items())),
        "top_ticker_row_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "parameters": {
            "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
            "min_eps_estimate_revision_20d_pct": MIN_EPS_ESTIMATE_REVISION_20D_PCT,
            "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
            "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
        },
        "source_caveat": (
            "Daily earnings snapshots are replayable; historical estimate "
            "values remain proxy-grade until a PIT vendor/provenance adapter is "
            "added."
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
    revision_context = _load_revision_context(universe, frames)
    rows_by_date_ticker = revision_context["rows_by_date_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
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
            signal_date = str(asof.date())
            revision_row = rows_by_date_ticker.get(signal_date, {}).get(ticker)
            if revision_row is None:
                continue
            raw_pass_counts["snapshot_revision_row"] += 1
            revision = _float(revision_row.get("eps_estimate_revision_20d_pct"))
            days_to_earnings = _float(revision_row.get("days_to_earnings"))
            if revision is None or days_to_earnings is None:
                reject_counts["missing_revision_or_dte"] += 1
                continue
            if revision < MIN_EPS_ESTIMATE_REVISION_20D_PCT:
                reject_counts["revision_below_threshold"] += 1
                continue
            if not (MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS):
                reject_counts["days_to_earnings_outside_window"] += 1
                continue
            raw_pass_counts["revision_velocity_passed"] += 1

            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
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

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            score = (
                min(revision, 0.50) * 10.0
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
                "prior_snapshot_date": revision_row.get("prior_snapshot_date"),
                "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
                "eps_estimate_current": revision_row.get("eps_estimate_current"),
                "eps_estimate_prior": revision_row.get("eps_estimate_prior"),
                "eps_estimate_revision_20d_pct": framework._round(revision, 6),
                "days_to_earnings": framework._round(days_to_earnings, 2),
                "avg_historical_surprise_pct": revision_row.get("avg_historical_surprise_pct"),
                "positive_surprise_count": revision_row.get("positive_surprise_count"),
                "surprise_history_count": revision_row.get("surprise_history_count"),
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "same_day_core_entry_count": len(same_day_core),
                "same_ticker_core_overlap": False,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
                "source_caveat": revision_row.get("source_caveat"),
            }
            if len(examples) < 20:
                examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "revision_20d": candidate["eps_estimate_revision_20d_pct"],
                        "days_to_earnings": candidate["days_to_earnings"],
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
                -float(item["eps_estimate_revision_20d_pct"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "revision_reject_counts": dict(sorted(reject_counts.items())),
        "revision_examples": examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    revision_context = _REVISION_CACHE or {}
    framework._write_json(
        REVISION_ROWS_JSON,
        _revision_rows_summary(revision_context.get("rows", [])),
    )
    framework._write_json(REVISION_FILES_JSON, revision_context.get("files", []))

    numeric_passed = bool(payload["gate4"]["passed"])
    promotable_source = False
    passed = numeric_passed and promotable_source
    if numeric_passed:
        decision = "positive_proxy_lead_not_retained_requires_pit_revision_source"
        rationale = (
            "Numeric Gate 4 passed, but the historical EPS-estimate snapshot "
            "source is proxy-grade. Do not retain or promote until a shared "
            "PIT analyst-revision adapter proves production/backtest parity."
        )
    else:
        decision = "rejected_analyst_revision_velocity_candidate_pool"
        rationale = "Gate 4 failed; no production or shared policy behavior is retained."
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "Positive 20-trading-day EPS estimate revision velocity in "
                "daily earnings snapshots, combined with liquid breakout "
                "confirmation, may identify higher-quality default-off paper "
                "candidates than generic pre-earnings surprise thresholds."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260531-001",
                "exp-20260531-003",
                "exp-20260604-001",
                "exp-20260602-023",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "daily_earnings_snapshot_eps_estimate_revision_velocity",
            "interpretation": rationale,
            "rejection_reason": None if numeric_passed else "; ".join(payload["gate4"]["failed_gates"]),
            "prediction": {
                "success_probability": 0.24,
                "expected_ev_delta": 0.12,
                "expected_pnl_delta": 2500.0,
                "main_failure_modes": [
                    "late_strong_regression",
                    "proxy_snapshot_provenance",
                    "overlaps_existing_pead_stack",
                    "concentration_failed",
                    "estimate_revision_noise",
                ],
                "confidence_reason": (
                    "Analyst revision is underdeveloped and the no-artifact "
                    "viability count found hundreds of 20d positive-revision "
                    "rows per canonical window, but historical snapshot "
                    "provenance is proxy-grade."
                ),
                "recorded_at": "2026-06-04T23:22:47+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.24 - actual_success) ** 2, 6),
            },
            "earnings_revision_source": {
                "source": revision_context.get("source"),
                "row_count": len(revision_context.get("rows", [])),
                "file_count": len(revision_context.get("files", [])),
                "rows_artifact": framework._repo_rel(REVISION_ROWS_JSON),
                "files_artifact": framework._repo_rel(REVISION_FILES_JSON),
                "source_caveat": revision_context.get("source_caveat"),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Ticker must have daily earnings snapshot EPS estimate revision "
                "over the prior 20 trading snapshots >= 3%, days_to_earnings "
                "between 7 and 60, and fixed liquid breakout confirmation."
            ),
            "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
            "min_eps_estimate_revision_20d_pct": MIN_EPS_ESTIMATE_REVISION_20D_PCT,
            "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
            "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: analyst estimate revision velocity should "
            "capture upstream expectation adjustment before it is fully priced."
        ),
        "2_history_check": {
            "exp-20260531-001": (
                "Pre-earnings surprise/revision/RS was negative; this run uses "
                "20d estimate revision velocity rather than imminent surprise."
            ),
            "exp-20260531-003": (
                "Imminent earnings surprise/RS was high variance and breached "
                "late_strong/drawdown; this run avoids 1-7 day event chasing."
            ),
            "exp-20260604-001": (
                "Latest-vs-average surprise support failed; this run uses EPS "
                "estimate trajectory, not another surprise scalar."
            ),
            "exp-20260602-023": (
                "Post-earnings underpriced positive-surprise drift is accepted "
                "as a separate PEAD sleeve; this run is a pre-event revision "
                "candidate pool and remains default-off."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample, drawdown, survival, "
            "and concentration guards pass; source provenance must be shared "
            "and parity-safe before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260604_029_analyst_revision_velocity_candidate_pool.py"
        ),
    }
    payload["gate2"].update(
        {
            "minimum_open_position_fields_checked": ["entry_date", "target_price"],
            "earnings_snapshot_required_fields": [
                "eps_estimate",
                "days_to_earnings",
                "historical_surprise_pct",
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
            "production_data_fetch_changed": False,
            "requires_shared_adapter_before_promotion": numeric_passed,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "source_provenance_promotable": promotable_source,
        "parity_note": (
            "This runner changes no production path. Because historical EPS "
            "estimate snapshots are proxy-grade, even a numeric pass is only "
            "a research lead until a shared PIT analyst-revision source and "
            "backtest/production parity tests exist."
        ),
    }
    payload["next_retry_requires"] = (
        "If rejected, do not retune nearby revision/DTE thresholds on the "
        "frozen sample; valid next work is a PIT analyst-estimate source with "
        "revision persistence/analyst-count trajectory, or forward replacement "
        "rows for this proxy lead."
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(REVISION_ROWS_JSON),
        framework._repo_rel(REVISION_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    payload["gate4"]["numeric_passed"] = numeric_passed
    payload["gate4"]["passed"] = passed
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["gate4"]["requires_parity_before_promotion"] = numeric_passed
    payload["gate4"]["source_provenance_guard"] = {
        "promotable_source": promotable_source,
        "reason": "historical EPS estimate snapshots are proxy-grade",
    }
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Analyst Revision Velocity Candidate Pool",
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
        f"- numeric Gate 4 passed: `{gate4.get('numeric_passed')}`",
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
            "The tested fields are daily earnings-snapshot EPS estimates, "
            "same-day/prior OHLCV, and SPY relative strength. The result is "
            "replay-only/default-off: no production entry, ranking, sizing, "
            "exit, LLM/news, watchlist, or order behavior changed.",
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
