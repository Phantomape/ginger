"""exp-20260531-001: pre-earnings surprise/revision RS paper sleeve.

This alpha search tests one stock-only, production-visible, free-data
candidate source. A ticker can enter a default-off paper sleeve when the
canonical daily earnings snapshot shows it is 22-45 calendar days before
earnings, has durable positive historical surprise behavior, has a 30-calendar
day EPS estimate upgrade, and its OHLCV tape confirms liquidity, trend, and
relative strength.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework
from data_paths import daily_artifact_glob


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-001"
STEM = "pre_earnings_surprise_revision_rs_candidate_pool"
TRIAL_FAMILY = "earnings_snapshot_pre_earnings_surprise_revision_rs_candidate_pool"
CHANGED_VARIABLE = "earnings_snapshot_pre_earnings_surprise_revision_rs_candidate_source_v1"
RULE_VERSION = "pre_earnings_22_45_surprise_revision_rs_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_001_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

DAYS_TO_EARNINGS_MIN = 22
DAYS_TO_EARNINGS_MAX = 45
EPS_ESTIMATE_LOOKBACK_CALENDAR_DAYS = 30
MIN_AVG_HISTORICAL_SURPRISE_PCT = 5.0
MIN_POSITIVE_SURPRISE_COUNT = 3
MIN_SURPRISE_HISTORY_COUNT = 4
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_RS20_VS_SPY = 0.0
MIN_CLOSE_LOCATION = 0.55
MIN_EPS_ESTIMATE_DELTA_30D = 0.0
PCT_DELTA_PRIOR_FLOOR = 0.05

_EARNINGS_INDEX_CACHE: dict[str, list[tuple[str, dict[str, Any]]]] | None = None
_EARNINGS_DATE_COUNT = 0


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = DOC_TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _snapshot_date_from_path(path: Path) -> str:
    token = path.stem.rsplit("_", 1)[-1]
    if len(token) != 8 or not token.isdigit():
        raise ValueError(f"unrecognised earnings snapshot filename: {path.name}")
    return f"{token[:4]}-{token[4:6]}-{token[6:8]}"


def _load_earnings_index() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    global _EARNINGS_DATE_COUNT, _EARNINGS_INDEX_CACHE
    if _EARNINGS_INDEX_CACHE is not None:
        return _EARNINGS_INDEX_CACHE

    by_ticker: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    dates_seen: set[str] = set()
    for path in daily_artifact_glob("earnings_snapshot"):
        if "legacy_root" in path.parts:
            continue
        snap_date = _snapshot_date_from_path(path)
        dates_seen.add(snap_date)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        earnings = payload.get("earnings") or {}
        if not isinstance(earnings, dict):
            continue
        for raw_ticker, info in earnings.items():
            if not isinstance(info, dict):
                continue
            ticker = str(raw_ticker).upper().strip()
            if not ticker:
                continue
            by_ticker.setdefault(ticker, []).append((snap_date, info))

    for rows in by_ticker.values():
        rows.sort(key=lambda pair: pair[0])
    _EARNINGS_DATE_COUNT = len(dates_seen)
    _EARNINGS_INDEX_CACHE = by_ticker
    return by_ticker


def _calendar_days_before(iso_date: str, days: int) -> str:
    return (date.fromisoformat(iso_date) - timedelta(days=days)).isoformat()


def _earnings_info_at_or_before(ticker: str, iso_date: str) -> tuple[str | None, dict[str, Any] | None]:
    rows = _load_earnings_index().get(str(ticker).upper().strip(), [])
    best: tuple[str, dict[str, Any]] | None = None
    for snap_date, info in rows:
        if snap_date > iso_date:
            break
        best = (snap_date, info)
    if best is None:
        return (None, None)
    return best


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _eps_estimate_delta_30d(ticker: str, signal_date: str) -> dict[str, Any] | None:
    current_snap, current_info = _earnings_info_at_or_before(ticker, signal_date)
    if current_info is None:
        return None
    prior_cutoff = _calendar_days_before(signal_date, EPS_ESTIMATE_LOOKBACK_CALENDAR_DAYS)
    prior_snap, prior_info = _earnings_info_at_or_before(ticker, prior_cutoff)
    current_estimate = _float_or_none(current_info.get("eps_estimate"))
    prior_estimate = _float_or_none(prior_info.get("eps_estimate") if prior_info else None)
    if current_estimate is None or prior_estimate is None:
        return None
    delta = current_estimate - prior_estimate
    pct_delta = None
    if abs(prior_estimate) >= PCT_DELTA_PRIOR_FLOOR:
        pct_delta = delta / abs(prior_estimate)
    return {
        "earnings_snapshot_source_date": current_snap,
        "eps_estimate": current_estimate,
        "eps_estimate_prior_30d": prior_estimate,
        "eps_estimate_prior_30d_source_date": prior_snap,
        "eps_estimate_delta_30d": delta,
        "eps_estimate_pct_delta_30d": pct_delta,
    }


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, field: str) -> float | None:
    if idx < days:
        return None
    values = [framework.ohlcv_helper._value(row, field) for row in rows[idx - days:idx]]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = framework.ohlcv_helper._value(rows[start_idx], "Close")
    end = framework.ohlcv_helper._value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (float(end) / float(start)) - 1.0


def _surprise_context(info: dict[str, Any]) -> dict[str, Any] | None:
    history_raw = info.get("historical_surprise_pct") or []
    if not isinstance(history_raw, list):
        return None
    history = [_float_or_none(value) for value in history_raw]
    clean = [float(value) for value in history if value is not None]
    avg_surprise = _float_or_none(info.get("avg_historical_surprise_pct"))
    if avg_surprise is None and clean:
        avg_surprise = sum(clean) / len(clean)
    if avg_surprise is None:
        return None
    positive_count = sum(1 for value in clean if value > 0)
    return {
        "avg_historical_surprise_pct": avg_surprise,
        "historical_surprise_count": len(clean),
        "positive_historical_surprise_count": positive_count,
        "historical_surprise_pct": clean,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = [
        date_value
        for date_value in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    min_idx = max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)

    for ticker in sorted(set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS)):
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for signal_date in dates:
            idx = idx_by_date.get(signal_date)
            spy_idx = spy_index.get(signal_date)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
                audit["insufficient_ohlcv_history"] += 1
                continue

            snap_date, earnings_info = _earnings_info_at_or_before(ticker, signal_date)
            if earnings_info is None:
                audit["missing_earnings_snapshot_row"] += 1
                continue
            days_to_earnings = _float_or_none(earnings_info.get("days_to_earnings"))
            if days_to_earnings is None:
                audit["missing_days_to_earnings"] += 1
                continue
            if not (DAYS_TO_EARNINGS_MIN <= days_to_earnings <= DAYS_TO_EARNINGS_MAX):
                audit["outside_pre_earnings_window"] += 1
                continue

            surprise = _surprise_context(earnings_info)
            if surprise is None:
                audit["missing_surprise_history"] += 1
                continue
            if surprise["historical_surprise_count"] < MIN_SURPRISE_HISTORY_COUNT:
                audit["insufficient_surprise_history"] += 1
                continue
            if surprise["positive_historical_surprise_count"] < MIN_POSITIVE_SURPRISE_COUNT:
                audit["not_durable_positive_surprise"] += 1
                continue
            if surprise["avg_historical_surprise_pct"] < MIN_AVG_HISTORICAL_SURPRISE_PCT:
                audit["avg_surprise_too_low"] += 1
                continue

            eps_delta = _eps_estimate_delta_30d(ticker, signal_date)
            if eps_delta is None:
                audit["missing_eps_estimate_delta_30d"] += 1
                continue
            if eps_delta["eps_estimate_delta_30d"] <= MIN_EPS_ESTIMATE_DELTA_30D:
                audit["eps_estimate_not_upgraded_30d"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if not close or volume is None:
                audit["missing_close_or_volume"] += 1
                continue
            avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
            if avg_dollar_volume is None:
                audit["missing_avg_dollar_volume"] += 1
                continue
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                audit["low_avg_dollar_volume"] += 1
                continue

            ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if ma50 is None or float(close) <= ma50:
                audit["below_50d_trend"] += 1
                continue
            close_location = framework._close_location(rows[idx])
            if close_location is None or close_location < MIN_CLOSE_LOCATION:
                audit["weak_close_location"] += 1
                continue

            ret20 = _close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret20 = _close_return(spy_rows, spy_idx - RELATIVE_STRENGTH_DAYS, spy_idx)
            if ret20 is None or spy_ret20 is None:
                audit["missing_relative_strength"] += 1
                continue
            rs20_vs_spy = ret20 - spy_ret20
            if rs20_vs_spy <= MIN_RS20_VS_SPY:
                audit["rs20_not_positive_vs_spy"] += 1
                continue

            ab_entries = entries_by_date.get(signal_date, [])
            pct_delta = eps_delta["eps_estimate_pct_delta_30d"]
            surprise_bucket = (
                "very_high_predictability"
                if surprise["avg_historical_surprise_pct"] >= 15.0
                else "positive_predictability"
            )
            score = (
                (pct_delta if isinstance(pct_delta, (int, float)) else 0.0)
                + (surprise["avg_historical_surprise_pct"] / 100.0)
                + rs20_vs_spy
            )
            candidates.append(
                {
                    "ticker": ticker,
                    "date": signal_date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                    "ma50": framework.base._round(ma50, 4),
                    "close_location": framework.base._round(close_location, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                    "days_to_earnings": int(days_to_earnings),
                    "earnings_snapshot_source_date": snap_date,
                    "avg_historical_surprise_pct": framework.base._round(
                        surprise["avg_historical_surprise_pct"], 6
                    ),
                    "historical_surprise_count": surprise["historical_surprise_count"],
                    "positive_historical_surprise_count": surprise[
                        "positive_historical_surprise_count"
                    ],
                    "surprise_predictability_bucket": surprise_bucket,
                    "eps_estimate": framework.base._round(eps_delta["eps_estimate"], 6),
                    "eps_estimate_prior_30d": framework.base._round(
                        eps_delta["eps_estimate_prior_30d"], 6
                    ),
                    "eps_estimate_delta_30d": framework.base._round(
                        eps_delta["eps_estimate_delta_30d"], 6
                    ),
                    "eps_estimate_pct_delta_30d": framework.base._round(pct_delta, 6)
                    if isinstance(pct_delta, (int, float))
                    else None,
                    "eps_estimate_prior_30d_source_date": eps_delta[
                        "eps_estimate_prior_30d_source_date"
                    ],
                    "pre_earnings_revision_surprise_score": framework.base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_earnings_snapshot_and_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["pre_earnings_revision_surprise_score"]),
            -float(row["eps_estimate_delta_30d"]),
            -float(row["avg_historical_surprise_pct"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "earnings_snapshot_dates_loaded": _EARNINGS_DATE_COUNT,
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_pre_earnings_surprise_revision_rs_candidate_pool"
        if gate4["passed"]
        else "rejected_pre_earnings_surprise_revision_rs_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.15,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "sample_too_thin",
            "PEAD_or_pre_earnings_instability",
            "concentration",
            "old_thin_regression",
        ],
        "confidence_reason": (
            "Daily earnings snapshots cover all canonical windows and the source is "
            "free plus production-visible, but nearby PEAD and revision experiments "
            "were unstable or concentrated."
        ),
        "recorded_at": "2026-05-31T00:08:44+00:00",
        "brier_score": round((0.18 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Pre-earnings stocks with durable positive historical surprise, "
                "30-day EPS estimate upgrades, and OHLCV RS/liquidity confirmation "
                "may add a production-visible free-data candidate-pool sleeve."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "expectation_pre_earnings_drift",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 8,
            "nearby_prior_experiments": [
                "exp-20260508-001",
                "exp-20260508-013",
                "exp-20260528-027",
                "exp-20260528-028",
                "exp-20260529-007",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "daily_earnings_snapshot_free_data_plus_ohlcv_rs_confirmation",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "days_to_earnings_min": DAYS_TO_EARNINGS_MIN,
                "days_to_earnings_max": DAYS_TO_EARNINGS_MAX,
                "eps_estimate_lookback_calendar_days": EPS_ESTIMATE_LOOKBACK_CALENDAR_DAYS,
                "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
                "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
                "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_close_location": MIN_CLOSE_LOCATION,
                "min_eps_estimate_delta_30d": MIN_EPS_ESTIMATE_DELTA_30D,
                "source_definition": [
                    "canonical daily earnings snapshot row exists at or before signal date",
                    "days_to_earnings is between 22 and 45",
                    "at least 4 historical surprise observations",
                    "at least 3 historical surprises are positive",
                    "average historical surprise percent >= 5",
                    "EPS estimate at signal date exceeds PIT estimate from 30 calendar days earlier",
                    "ticker closes above prior 50-day moving average",
                    "20-day return exceeds SPY",
                    "20-day average dollar volume >= 40 million",
                    "signal-day close location >= 0.55",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "pre_earnings_revision_surprise_score desc",
                    "eps_estimate_delta_30d desc",
                    "avg_historical_surprise_pct desc",
                    "rs20_vs_spy desc",
                    "avg_dollar_volume_20d desc",
                    "ticker asc",
                ],
                "locked_variables": [
                    "core universe membership",
                    "core signal generation",
                    "core ranking",
                    "core position sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "watchlists",
                    "live/default orders",
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: durable positive surprise history plus "
                    "pre-earnings estimate upgrades should identify names with "
                    "underwritten expectation drift when price/RS already confirms."
                ),
                "2_history_check": {
                    "exp-20260508-001": (
                        "Pre-earnings 22-45 day risk add was positive in aggregate "
                        "but regressed old_thin and was only a risk replay. This run "
                        "adds surprise/revision quality as a new candidate source."
                    ),
                    "exp-20260508-013": (
                        "Pre-earnings 8-21 day variants regressed aggregate or key "
                        "windows. This run keeps the 22-45 day phase and tests a "
                        "different information source."
                    ),
                    "exp-20260528-027_028": (
                        "PEAD-window residual/no-residual variants were rejected. "
                        "This is pre-earnings drift, not a PEAD-window retest."
                    ),
                    "exp-20260529-007": (
                        "Revision magnitude alone was unstable. This run requires "
                        "durable surprise history and OHLCV confirmation, not a "
                        "magnitude-only bucket."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                    "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                    ">=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_001_pre_earnings_surprise_revision_rs_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay attribution remains sparse. "
                "Skipped Companyfacts/VBB/VCP/FINRA/state-surface scalar retunes "
                "because the playbook requires forward rows or materially new fields. "
                "This tests a different free-data candidate-pool source and changes "
                "one candidate-source variable only."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If accepted, promotion would "
                    "require a shared default-off adapter using quant/data_paths.py "
                    "daily earnings snapshots and parity tests before any live or "
                    "core-ranking consumer uses the field."
                ),
            },
            "interpretation": (
                "The pre-earnings surprise/revision RS sleeve cleared Gate 4 as a "
                "default-off replay lead; no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The pre-earnings surprise/revision RS sleeve did not clear Gate 4. "
                    "Do not promote it or retry adjacent pre-earnings surprise/revision "
                    "thresholds on the frozen windows without new forward rows or a "
                    "different expectation-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use closed forward replacement-value rows or a richer "
                "production-visible expectation field such as current surprise, guidance, "
                "or estimate dispersion; do not threshold-mine this frozen sample."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Earnings snapshot fields are read from canonical daily snapshots dated at "
        "or before the signal date. OHLCV confirmation is observed through the "
        "signal-date close; paper entry is the next available open with production "
        "entry slippage; exit is ten trading days after the signal with target-side "
        "sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "earnings_snapshots": {
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "snapshots_loaded": _EARNINGS_DATE_COUNT,
            "required_fields": [
                "days_to_earnings",
                "eps_estimate",
                "historical_surprise_pct",
                "avg_historical_surprise_pct",
            ],
            "tickers_with_snapshot_rows": len(_load_earnings_index()),
        }
    }
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "days_to_earnings",
            "avg_historical_surprise_pct",
            "positive_historical_surprise_count",
            "eps_estimate_delta_30d",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260531-001 Pre-Earnings Surprise/Revision RS Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source using canonical earnings snapshots plus OHLCV confirmation, top-1 per day, next-open entry, ten-trading-day exit.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Pre-earnings surprise/revision RS candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_json(DOC_TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_report(payload))
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
