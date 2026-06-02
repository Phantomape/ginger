"""exp-20260602-018: sector-relative risk-adjusted momentum candidate pool.

This alpha search tests one stock-only, free-OHLCV default-off paper source.
It looks for production-universe stocks whose 60-day return is strong versus
both SPY and same-sector peers while 20-day volatility is not materially above
the sector median. The source is replay-only: core signal generation, ranking,
sizing, exits, LLM/news replay, watchlists, and live/default orders are
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework
from broad_market_sector_map import (
    RULE_VERSION as SECTOR_MAP_RULE_VERSION,
    coverage_report,
    load_cache,
    lookup_sector,
)


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-018"
STEM = "sector_relative_risk_adjusted_momentum"
TRIAL_FAMILY = "sector_relative_risk_adjusted_momentum"
CHANGED_VARIABLE = "sector_relative_risk_adjusted_momentum_candidate_pool_v1"
RULE_VERSION = "sector_residual_rs60_low_vol_top1_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_018_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RS_DAYS = 60
SHORT_RS_DAYS = 20
VOL_DAYS = 20
MOVING_AVERAGE_DAYS = 50
AVG_DOLLAR_VOLUME_DAYS = 20
NEAR_HIGH_LOOKBACK_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20D = 30_000_000.0
MIN_RET60_VS_SPY = 0.02
MIN_RET60_VS_SECTOR = 0.025
MIN_RET20_VS_SECTOR = 0.0
MAX_VOL20_VS_SECTOR_MEDIAN = 1.10
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MIN_CLOSE_VS_PRIOR_20D_HIGH = 0.95
MIN_SECTOR_MEMBER_COUNT = 3
MIN_RISK_ADJUSTED_SCORE = 0.03

MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = framework.EXCLUDED_TICKERS


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(framework.base._safe(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    framework.DOC_TICKET_JSON = (
        REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework._candidate_rows_for_window = _candidate_rows_for_window


def _sector_maps(universe: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cache = load_cache()
    lookups = {
        ticker: lookup_sector(ticker, cache)
        for ticker in sorted(set(universe).difference(EXCLUDED_TICKERS))
    }
    sectors: dict[str, list[str]] = {}
    for ticker, row in lookups.items():
        sector = row.get("sector")
        if row.get("status") == "ok" and sector:
            sectors.setdefault(str(sector), []).append(ticker)
    return lookups, sectors, coverage_report(universe, cache)


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            continue
        values.append(float(close) * float(volume))
    if len(values) < days:
        return None
    return sum(values) / len(values)


def _daily_returns(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> list[float]:
    if start_idx < 0 or end_idx >= len(rows):
        return []
    values: list[float] = []
    for idx in range(start_idx + 1, end_idx + 1):
        previous_close = framework.ohlcv_helper._value(rows[idx - 1], "Close")
        close = framework.ohlcv_helper._value(rows[idx], "Close")
        if not previous_close or close is None:
            continue
        values.append(float(close) / float(previous_close) - 1.0)
    return values


def _realized_volatility(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    returns = _daily_returns(rows, idx - days, idx)
    if len(returns) < days:
        return None
    if len(returns) < 2:
        return None
    return statistics.pstdev(returns) * math.sqrt(days)


def _sector_context(
    snapshot: dict[str, list[dict[str, Any]]],
    sector_tickers: list[str],
    date: str,
) -> dict[str, Any] | None:
    ret60_values: list[float] = []
    ret20_values: list[float] = []
    vol20_values: list[float] = []
    for ticker in sector_tickers:
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx = framework.ohlcv_helper._row_index(rows).get(date)
        if idx is None or idx < RS_DAYS:
            continue
        ret60 = framework._close_return(rows, idx - RS_DAYS, idx)
        ret20 = framework._close_return(rows, idx - SHORT_RS_DAYS, idx)
        vol20 = _realized_volatility(rows, idx, VOL_DAYS)
        if ret60 is not None:
            ret60_values.append(float(ret60))
        if ret20 is not None:
            ret20_values.append(float(ret20))
        if vol20 is not None:
            vol20_values.append(float(vol20))
    if (
        len(ret60_values) < MIN_SECTOR_MEMBER_COUNT
        or len(ret20_values) < MIN_SECTOR_MEMBER_COUNT
        or len(vol20_values) < MIN_SECTOR_MEMBER_COUNT
    ):
        return None
    return {
        "sector_member_count": len(ret60_values),
        "sector_ret60_median": statistics.median(ret60_values),
        "sector_ret20_median": statistics.median(ret20_values),
        "sector_vol20_median": statistics.median(vol20_values),
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    sector_lookup, sector_tickers, sector_coverage = _sector_maps(universe)
    sector_context_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    min_idx = max(
        RS_DAYS,
        SHORT_RS_DAYS,
        VOL_DAYS,
        MOVING_AVERAGE_DAYS,
        AVG_DOLLAR_VOLUME_DAYS,
        NEAR_HIGH_LOOKBACK_DAYS,
    )

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        lookup = sector_lookup.get(ticker) or {}
        sector = lookup.get("sector")
        if lookup.get("status") != "ok" or not sector:
            audit["missing_sector_lookup"] += len(dates)
            continue
        peer_tickers = [
            peer
            for peer in sector_tickers.get(str(sector), [])
            if peer in snapshot and peer != ticker
        ]
        if len(peer_tickers) + 1 < MIN_SECTOR_MEMBER_COUNT:
            audit["thin_sector_peer_group"] += len(dates)
            continue

        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < RS_DAYS:
                audit["insufficient_history"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if not close or volume is None:
                audit["missing_close_or_volume"] += 1
                continue

            avg_dollar_volume = _avg_dollar_volume(
                rows,
                idx,
                AVG_DOLLAR_VOLUME_DAYS,
            )
            if avg_dollar_volume is None:
                audit["missing_avg_dollar_volume"] += 1
                continue
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                audit["low_avg_dollar_volume"] += 1
                continue

            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if ma50 is None or float(close) <= ma50:
                audit["not_above_ma50"] += 1
                continue

            prior_high_20d = framework._prior_high(
                rows,
                idx,
                NEAR_HIGH_LOOKBACK_DAYS,
                "High",
            )
            if not prior_high_20d:
                audit["missing_near_high_context"] += 1
                continue
            close_vs_prior_high = float(close) / float(prior_high_20d)
            if close_vs_prior_high < MIN_CLOSE_VS_PRIOR_20D_HIGH:
                audit["not_near_prior_20d_high"] += 1
                continue

            close_location = framework._close_location(rows[idx])
            if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
                audit["weak_signal_close_location"] += 1
                continue

            ret60 = framework._close_return(rows, idx - RS_DAYS, idx)
            ret20 = framework._close_return(rows, idx - SHORT_RS_DAYS, idx)
            spy_ret60 = framework._close_return(spy_rows, spy_idx - RS_DAYS, spy_idx)
            spy_ret20 = framework._close_return(
                spy_rows,
                spy_idx - SHORT_RS_DAYS,
                spy_idx,
            )
            vol20 = _realized_volatility(rows, idx, VOL_DAYS)
            if any(value is None for value in (ret60, ret20, spy_ret60, spy_ret20, vol20)):
                audit["missing_return_or_volatility"] += 1
                continue

            context_key = (date, str(sector))
            if context_key not in sector_context_cache:
                sector_context_cache[context_key] = _sector_context(
                    snapshot,
                    sector_tickers.get(str(sector), []),
                    date,
                )
            sector_context = sector_context_cache[context_key]
            if not sector_context:
                audit["missing_sector_context"] += 1
                continue

            ret60_vs_spy = float(ret60) - float(spy_ret60)
            ret20_vs_spy = float(ret20) - float(spy_ret20)
            ret60_vs_sector = float(ret60) - float(sector_context["sector_ret60_median"])
            ret20_vs_sector = float(ret20) - float(sector_context["sector_ret20_median"])
            vol20_vs_sector = float(vol20) / max(
                float(sector_context["sector_vol20_median"]),
                1e-9,
            )
            if ret60_vs_spy < MIN_RET60_VS_SPY:
                audit["ret60_vs_spy_too_weak"] += 1
                continue
            if ret60_vs_sector < MIN_RET60_VS_SECTOR:
                audit["ret60_vs_sector_too_weak"] += 1
                continue
            if ret20_vs_sector < MIN_RET20_VS_SECTOR:
                audit["ret20_vs_sector_too_weak"] += 1
                continue
            if vol20_vs_sector > MAX_VOL20_VS_SECTOR_MEDIAN:
                audit["vol20_above_sector_guardrail"] += 1
                continue

            risk_adjusted_score = (
                ret60_vs_sector
                + 0.50 * ret20_vs_sector
                + 0.50 * ret60_vs_spy
                - 0.05 * max(0.0, vol20_vs_sector - 1.0)
            )
            if risk_adjusted_score < MIN_RISK_ADJUSTED_SCORE:
                audit["risk_adjusted_score_too_low"] += 1
                continue

            ab_entries = entries_by_date.get(date, [])
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "sector": str(sector),
                    "industry": lookup.get("industry"),
                    "sector_map_rule_version": SECTOR_MAP_RULE_VERSION,
                    "sector_member_count": sector_context["sector_member_count"],
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(
                        avg_dollar_volume,
                        2,
                    ),
                    "ma50": framework.base._round(ma50, 4),
                    "prior_high_20d": framework.base._round(prior_high_20d, 4),
                    "close_vs_prior_high_20d": framework.base._round(
                        close_vs_prior_high,
                        6,
                    ),
                    "signal_close_location": framework.base._round(
                        close_location,
                        6,
                    ),
                    "ret60": framework.base._round(ret60, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret60": framework.base._round(spy_ret60, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "ret60_vs_spy": framework.base._round(ret60_vs_spy, 6),
                    "ret20_vs_spy": framework.base._round(ret20_vs_spy, 6),
                    "sector_ret60_median": framework.base._round(
                        sector_context["sector_ret60_median"],
                        6,
                    ),
                    "sector_ret20_median": framework.base._round(
                        sector_context["sector_ret20_median"],
                        6,
                    ),
                    "sector_vol20_median": framework.base._round(
                        sector_context["sector_vol20_median"],
                        6,
                    ),
                    "ret60_vs_sector": framework.base._round(ret60_vs_sector, 6),
                    "ret20_vs_sector": framework.base._round(ret20_vs_sector, 6),
                    "vol20": framework.base._round(vol20, 6),
                    "vol20_vs_sector": framework.base._round(vol20_vs_sector, 6),
                    "risk_adjusted_score": framework.base._round(
                        risk_adjusted_score,
                        6,
                    ),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["risk_adjusted_score"]),
            -float(row["ret60_vs_sector"]),
            -float(row["ret60_vs_spy"]),
            float(row["vol20_vs_sector"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "sector_coverage": sector_coverage,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_sector_relative_risk_adjusted_momentum_candidate_pool_lead"
        if gate4["passed"]
        else "rejected_sector_relative_risk_adjusted_momentum_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.25,
        "expected_pnl_delta": 12000.0,
        "main_failure_modes": [
            "raw_rs_duplicate",
            "noisy_pool",
            "trade_count_too_low",
            "drawdown_worse",
        ],
        "confidence_reason": (
            "Raw RS acceleration recently failed, but sector residual plus "
            "volatility cost is a distinct free-data discriminator that may "
            "reduce noise."
        ),
        "recorded_at": "2026-06-02T12:12:15+00:00",
        "brier_score": round((0.18 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Sector-relative risk-adjusted momentum candidates may expand "
                "the tradeable pool with less noise than raw RS acceleration by "
                "requiring same-sector leadership, positive SPY-adjusted trend, "
                "and lower realized volatility."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260602-015",
                "exp-20260525-916",
                "exp-20260526-010",
                "exp-20260526-015",
                "exp-20260527-022",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "free_pit_ohlcv_sector_relative_volatility_score"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "rs_days": RS_DAYS,
                "short_rs_days": SHORT_RS_DAYS,
                "vol_days": VOL_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "near_high_lookback_days": NEAR_HIGH_LOOKBACK_DAYS,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_ret60_vs_spy": MIN_RET60_VS_SPY,
                "min_ret60_vs_sector": MIN_RET60_VS_SECTOR,
                "min_ret20_vs_sector": MIN_RET20_VS_SECTOR,
                "max_vol20_vs_sector_median": MAX_VOL20_VS_SECTOR_MEDIAN,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "min_close_vs_prior_20d_high": MIN_CLOSE_VS_PRIOR_20D_HIGH,
                "min_sector_member_count": MIN_SECTOR_MEMBER_COUNT,
                "min_risk_adjusted_score": MIN_RISK_ADJUSTED_SCORE,
                "sector_map_rule_version": SECTOR_MAP_RULE_VERSION,
                "source_definition": [
                    "stock ticker only; no ETF/proxy tickers",
                    "20-day average dollar volume >= 30 million",
                    "offline deterministic yfinance sector cache status == ok",
                    "same-sector OHLCV peer count >= 3",
                    "close above prior 50-day moving average",
                    "close >= 95% of prior 20-day high",
                    "signal-day close location >= 0.55",
                    "60-day return exceeds SPY by at least 2.0%",
                    "60-day return exceeds sector median by at least 2.5%",
                    "20-day return does not lag sector median",
                    "20-day realized volatility <= 1.10x sector median",
                    "risk-adjusted sector score >= 3.0%",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "risk_adjusted_score desc",
                    "ret60_vs_sector desc",
                    "ret60_vs_spy desc",
                    "vol20_vs_sector asc",
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
                    "candidate_pool / entry: same-sector residual leaders with "
                    "reasonable realized volatility should produce cleaner "
                    "replacement candidates than raw RS acceleration."
                ),
                "2_history_check": {
                    "exp-20260602-015": (
                        "Raw RS acceleration candidate pool was rejected; this "
                        "run does not retune RS5/RS20 acceleration and instead "
                        "uses sector residual and volatility-normalized ranking."
                    ),
                    "sector_leadership_family": (
                        "Prior sector leadership and sector-breadth candidate "
                        "pools were rejected; this variant uses ticker-level "
                        "same-sector residual strength plus low-vol guardrail, "
                        "not sector breadth, same-sector core activity, or a "
                        "sector sleeve priority."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; at least two EV-improved windows; no survival rate "
                    "below 5%; drawdown drift <=0.5pp; >=20 paper trades across "
                    "all 3 windows; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_018_sector_relative_risk_adjusted_momentum.py"
                ),
            },
            "gate2": {
                **payload["gate2"],
                "target_trade_field_coverage": framework._field_coverage(
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
                        "sector",
                        "ret60_vs_spy",
                        "ret60_vs_sector",
                        "ret20_vs_sector",
                        "vol20_vs_sector",
                        "risk_adjusted_score",
                        "signal_close_location",
                        "avg_dollar_volume_20d",
                    ],
                ),
                "runtime_fields": [
                    "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                    "SPY OHLCV rows for same-window relative strength",
                    "offline deterministic broad_market_sector_map cache",
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                ],
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A retained result would require a shared default-off paper "
                    "adapter and parity tests before any daily report or live/"
                    "default behavior changes."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe joins remain "
                "sparse. Skipped Companyfacts support retunes because the "
                "current playbook asks for forward rows or materially new "
                "fields. Skipped SEC text/event retunes because financial-report "
                "language and 10-Q/SPY-context variants are already heavily "
                "tested. This run tests one free-OHLCV sector residual score."
            ),
            "interpretation": (
                "The sector-relative risk-adjusted momentum sleeve cleared Gate "
                "4 as a replay-only lead, but no production/shared policy was "
                "promoted."
                if gate4["passed"]
                else (
                    "The sector-relative risk-adjusted momentum sleeve did not "
                    "clear Gate 4. Do not promote it or retry nearby sector/RS/"
                    "volatility thresholds on these frozen windows without "
                    "forward paper rows or an orthogonal source-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or an orthogonal free-data "
                "quality field; do not simply retune sector residual/volatility "
                "thresholds."
            ),
            "anti_js": "No JavaScript was used.",
        }
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
            f"# {EXPERIMENT_ID} Sector-Relative Risk-Adjusted Momentum",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits stock-only sector-residual momentum candidates with a volatility guardrail, top-1 per day, next-open entry, ten-trading-day exit.",
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
            "",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    _write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    _write_json(LOG_JSON, payload)
    report = _build_report(payload)
    _write_text(ARTIFACT_MD, report)
    _write_text(CARD_MD, report)

    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)
    _write_manifest()


def _write_manifest() -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": _repo_rel(AFTER_AGG_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


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
                    "artifact": _repo_rel(ARTIFACT_MD),
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
