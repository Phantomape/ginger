"""exp-20260605-013: broad low-beta residual momentum candidate pool.

This alpha search tests one stock-only, free-OHLCV default-off paper source.
It looks for broad-universe stocks with strong 60-day residual momentum after
removing SPY beta, while avoiding high-correlation/high-beta momentum chases.
The source is replay-only: core signal generation, ranking, sizing, exits,
LLM/news replay, watchlists, and live/default orders are unchanged.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260602_018_sector_relative_risk_adjusted_momentum as source


REPO_ROOT = source.REPO_ROOT
framework = source.framework

EXPERIMENT_ID = "exp-20260605-013"
STEM = "broad_low_beta_residual_momentum"
TRIAL_FAMILY = "broad_low_beta_residual_momentum_candidate_pool"
CHANGED_VARIABLE = "broad_low_beta_residual_momentum_candidate_source_v1"
RULE_VERSION = "broad_low_beta_residual_momentum_60d_top1_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_013_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

RS_DAYS = 60
SHORT_RS_DAYS = 20
BETA_DAYS = 60
VOL_DAYS = 20
MOVING_AVERAGE_DAYS = 50
AVG_DOLLAR_VOLUME_DAYS = 20
NEAR_HIGH_LOOKBACK_DAYS = 20
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET60 = 0.04
MIN_RET60_VS_SPY = 0.01
MIN_RET20_VS_SPY = 0.0
MIN_RESIDUAL_RET60 = 0.06
MIN_IDIOSYNCRATIC_SCORE = 0.055
MAX_SPY_BETA_60D = 0.85
MAX_ABS_SPY_CORR_60D = 0.75
MAX_VOL20 = 0.10
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MIN_CLOSE_VS_PRIOR_20D_HIGH = 0.94

MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = source.EXCLUDED_TICKERS


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    source._write_text(path, text)


def _load_json(path: Path) -> dict[str, Any]:
    return source._load_json(path)


def _sha256(path: Path) -> str | None:
    return source._sha256(path)


def _return_stats(ticker_returns: list[float], spy_returns: list[float]) -> dict[str, float] | None:
    if len(ticker_returns) != len(spy_returns) or len(ticker_returns) < 50:
        return None
    mean_ticker = statistics.fmean(ticker_returns)
    mean_spy = statistics.fmean(spy_returns)
    centered_ticker = [value - mean_ticker for value in ticker_returns]
    centered_spy = [value - mean_spy for value in spy_returns]
    spy_var = sum(value * value for value in centered_spy)
    ticker_var = sum(value * value for value in centered_ticker)
    if spy_var <= 1e-12 or ticker_var <= 1e-12:
        return None
    cov = sum(a * b for a, b in zip(centered_ticker, centered_spy))
    beta = cov / spy_var
    corr = cov / math.sqrt(ticker_var * spy_var)
    return {"spy_beta_60d": beta, "spy_corr_60d": corr}


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
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    min_idx = max(
        RS_DAYS,
        SHORT_RS_DAYS,
        BETA_DAYS,
        VOL_DAYS,
        MOVING_AVERAGE_DAYS,
        AVG_DOLLAR_VOLUME_DAYS,
        NEAR_HIGH_LOOKBACK_DAYS,
    )

    for date in dates:
        spy_idx = spy_index.get(date)
        if spy_idx is None or spy_idx < min_idx:
            audit["missing_spy_history"] += 1
            continue
        spy_ret60 = framework._close_return(spy_rows, spy_idx - RS_DAYS, spy_idx)
        spy_ret20 = framework._close_return(spy_rows, spy_idx - SHORT_RS_DAYS, spy_idx)
        spy_returns = source._daily_returns(spy_rows, spy_idx - BETA_DAYS, spy_idx)
        if spy_ret60 is None or spy_ret20 is None or len(spy_returns) < 50:
            audit["missing_spy_return_context"] += 1
            continue

        for ticker in universe:
            if ticker in EXCLUDED_TICKERS or ticker == "SPY":
                audit["excluded_ticker"] += 1
                continue
            rows = framework.ohlcv_helper._series(snapshot, ticker)
            idx = framework.ohlcv_helper._row_index(rows).get(date)
            if idx is None or idx < min_idx:
                audit["missing_ticker_history"] += 1
                continue
            row = rows[idx]
            close = framework.ohlcv_helper._value(row, "Close")
            high = framework.ohlcv_helper._value(row, "High")
            low = framework.ohlcv_helper._value(row, "Low")
            volume = framework.ohlcv_helper._value(row, "Volume")
            if close is None or high is None or low is None or volume is None:
                audit["missing_ohlcv_field"] += 1
                continue
            close = float(close)
            high = float(high)
            low = float(low)
            volume = float(volume)
            if close < MIN_PRICE:
                audit["price_too_low"] += 1
                continue
            avg_dollar_volume = source._avg_dollar_volume(
                rows,
                idx,
                AVG_DOLLAR_VOLUME_DAYS,
            )
            if avg_dollar_volume is None or avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                audit["liquidity_too_low"] += 1
                continue
            ma50_values = [
                framework.ohlcv_helper._value(history_row, "Close")
                for history_row in rows[idx - MOVING_AVERAGE_DAYS:idx]
            ]
            if any(value is None for value in ma50_values) or len(ma50_values) < MOVING_AVERAGE_DAYS:
                audit["missing_ma50"] += 1
                continue
            ma50 = sum(float(value) for value in ma50_values if value is not None) / len(ma50_values)
            if close <= ma50:
                audit["below_ma50"] += 1
                continue
            prior_highs = [
                framework.ohlcv_helper._value(history_row, "High")
                for history_row in rows[idx - NEAR_HIGH_LOOKBACK_DAYS:idx]
            ]
            if any(value is None for value in prior_highs) or len(prior_highs) < NEAR_HIGH_LOOKBACK_DAYS:
                audit["missing_prior_high"] += 1
                continue
            prior_high_20d = max(float(value) for value in prior_highs if value is not None)
            close_vs_prior_high = close / prior_high_20d if prior_high_20d else 0.0
            if close_vs_prior_high < MIN_CLOSE_VS_PRIOR_20D_HIGH:
                audit["not_near_high"] += 1
                continue
            day_range = max(high - low, 1e-9)
            close_location = (close - low) / day_range
            if close_location < MIN_SIGNAL_CLOSE_LOCATION:
                audit["weak_close_location"] += 1
                continue
            ret60 = framework._close_return(rows, idx - RS_DAYS, idx)
            ret20 = framework._close_return(rows, idx - SHORT_RS_DAYS, idx)
            if ret60 is None or ret20 is None:
                audit["missing_return_context"] += 1
                continue
            ret60 = float(ret60)
            ret20 = float(ret20)
            if ret60 < MIN_RET60:
                audit["ret60_too_weak"] += 1
                continue
            ret60_vs_spy = ret60 - float(spy_ret60)
            ret20_vs_spy = ret20 - float(spy_ret20)
            if ret60_vs_spy < MIN_RET60_VS_SPY:
                audit["ret60_vs_spy_too_weak"] += 1
                continue
            if ret20_vs_spy < MIN_RET20_VS_SPY:
                audit["ret20_vs_spy_too_weak"] += 1
                continue
            ticker_returns = source._daily_returns(rows, idx - BETA_DAYS, idx)
            stats = _return_stats(ticker_returns, spy_returns)
            if stats is None:
                audit["missing_beta_context"] += 1
                continue
            beta = float(stats["spy_beta_60d"])
            corr = float(stats["spy_corr_60d"])
            if beta > MAX_SPY_BETA_60D:
                audit["beta_too_high"] += 1
                continue
            if abs(corr) > MAX_ABS_SPY_CORR_60D:
                audit["correlation_too_high"] += 1
                continue
            vol20 = source._realized_volatility(rows, idx, VOL_DAYS)
            if vol20 is None:
                audit["missing_vol20"] += 1
                continue
            vol20 = float(vol20)
            if vol20 > MAX_VOL20:
                audit["vol20_too_high"] += 1
                continue
            residual_ret60 = ret60 - beta * float(spy_ret60)
            if residual_ret60 < MIN_RESIDUAL_RET60:
                audit["residual_ret60_too_weak"] += 1
                continue
            idiosyncratic_score = residual_ret60 + 0.50 * ret20_vs_spy - 0.025 * abs(corr)
            if idiosyncratic_score < MIN_IDIOSYNCRATIC_SCORE:
                audit["idiosyncratic_score_too_low"] += 1
                continue

            ab_entries = entries_by_date.get(date, [])
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                    "ma50": framework.base._round(ma50, 4),
                    "prior_high_20d": framework.base._round(prior_high_20d, 4),
                    "close_vs_prior_high_20d": framework.base._round(close_vs_prior_high, 6),
                    "signal_close_location": framework.base._round(close_location, 6),
                    "ret60": framework.base._round(ret60, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret60": framework.base._round(spy_ret60, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "ret60_vs_spy": framework.base._round(ret60_vs_spy, 6),
                    "ret20_vs_spy": framework.base._round(ret20_vs_spy, 6),
                    "spy_beta_60d": framework.base._round(beta, 6),
                    "spy_corr_60d": framework.base._round(corr, 6),
                    "vol20": framework.base._round(vol20, 6),
                    "residual_ret60": framework.base._round(residual_ret60, 6),
                    "idiosyncratic_score": framework.base._round(idiosyncratic_score, 6),
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
            -float(row["idiosyncratic_score"]),
            -float(row["residual_ret60"]),
            float(row["spy_beta_60d"]),
            abs(float(row["spy_corr_60d"])),
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
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "positive_replay_lead_requires_shared_low_beta_adapter"
        if gate4["passed"]
        else "rejected_broad_low_beta_residual_momentum_candidate_pool"
    )
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.23,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "window_regression",
            "drawdown_drift",
            "hidden_beta_not_incremental",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Default-off paper adapters are historically strong, but broad "
            "OHLCV candidate pools and sector-risk-adjusted momentum were "
            "fragile; low-beta residual momentum is materially different "
            "enough for one pre-registered test."
        ),
        "recorded_at": "2026-06-05T07:05:37+00:00",
        "brier_score": round((0.23 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed" if gate4["passed"] else "rejected",
            "decision": decision,
            "accepted": bool(gate4["passed"]),
            "hypothesis": (
                "Broad liquid stocks with strong residual momentum but low "
                "SPY beta/correlation may add idiosyncratic default-off paper "
                "candidates beyond high-beta momentum."
            ),
            "change_summary": (
                "Tested a replay-only broad OHLCV low-beta residual-momentum "
                "top-1/day paper candidate source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260602-018",
                "exp-20260602-015",
                "exp-20260601-010",
                "exp-20260601-012",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "production_visible_free_ohlcv_hidden_beta_context",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "rs_days": RS_DAYS,
                "short_rs_days": SHORT_RS_DAYS,
                "beta_days": BETA_DAYS,
                "vol_days": VOL_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "near_high_lookback_days": NEAR_HIGH_LOOKBACK_DAYS,
                "min_price": MIN_PRICE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_ret60": MIN_RET60,
                "min_ret60_vs_spy": MIN_RET60_VS_SPY,
                "min_ret20_vs_spy": MIN_RET20_VS_SPY,
                "min_residual_ret60": MIN_RESIDUAL_RET60,
                "min_idiosyncratic_score": MIN_IDIOSYNCRATIC_SCORE,
                "max_spy_beta_60d": MAX_SPY_BETA_60D,
                "max_abs_spy_corr_60d": MAX_ABS_SPY_CORR_60D,
                "max_vol20": MAX_VOL20,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "min_close_vs_prior_20d_high": MIN_CLOSE_VS_PRIOR_20D_HIGH,
                "source_definition": [
                    "stock ticker only; no ETF/proxy tickers",
                    "price >= 10",
                    "20-day average dollar volume >= 50 million",
                    "close above prior 50-day moving average",
                    "close >= 94% of prior 20-day high",
                    "signal-day close location >= 0.55",
                    "60-day return >= 4%",
                    "60-day return exceeds SPY by at least 1%",
                    "20-day return does not lag SPY",
                    "60-day beta to SPY <= 0.85",
                    "absolute 60-day correlation to SPY <= 0.75",
                    "20-day realized volatility <= 10%",
                    "60-day residual return after beta-adjusting SPY >= 6%",
                    "idiosyncratic score >= 5.5%",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "idiosyncratic_score desc",
                    "residual_ret60 desc",
                    "spy_beta_60d asc",
                    "abs(spy_corr_60d) asc",
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
                    "candidate_pool / entry: broad stocks with positive "
                    "idiosyncratic momentum should add replacement candidates "
                    "without simply buying high-beta SPY followers."
                ),
                "2_history_check": {
                    "exp-20260602-018": (
                        "Sector-relative risk-adjusted momentum had adequate "
                        "sample but failed window and drawdown gates; this run "
                        "does not retune sector thresholds and instead removes "
                        "SPY beta/correlation directly."
                    ),
                    "exp-20260602-015": (
                        "Raw RS acceleration failed due momentum-chase "
                        "instability; this run avoids RS5/RS20 acceleration."
                    ),
                    "exp-20260601-010/012": (
                        "Broad gap/hold and undercut/reclaim OHLCV patterns "
                        "failed; this run is hidden-beta residual momentum, not "
                        "a renamed price-shape pattern."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "docs/backtesting.md canonical three-window Gate 4: EV and "
                    "PnL positive in all three windows, aggregate EV/PnL "
                    "positive, target sample and concentration pass, max "
                    "drawdown drift <= 0.5pp, survival unchanged."
                ),
                "5_reproducibility": (
                    "Runner, JSON artifact, before/after aggregate, log, card, "
                    "ticket, manifest, and JSONL record are written under "
                    f"{EXPERIMENT_ID}."
                ),
            },
            "field_reality_check": {
                "candidate_fields": framework._field_coverage(
                    [trade for trades in payload["target_trades_by_window"].values() for trade in trades],
                    [
                        "ticker",
                        "signal_date",
                        "entry_date",
                        "exit_date",
                        "entry_price",
                        "exit_price",
                        "pnl",
                        "known_at",
                        "ret60_vs_spy",
                        "ret20_vs_spy",
                        "spy_beta_60d",
                        "spy_corr_60d",
                        "residual_ret60",
                        "idiosyncratic_score",
                        "avg_dollar_volume_20d",
                    ],
                ),
                "runtime_fields": [
                    "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                    "SPY OHLCV rows for same-window beta and relative strength",
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
                "requires_shared_adapter_before_promotion": bool(gate4["passed"]),
                "parity_note": (
                    "This experiment changes no production code. A retained "
                    "positive result would require a shared default-off broad "
                    "low-beta residual-momentum paper adapter plus production/"
                    "backtest parity tests before any daily report queue, "
                    "candidate priority, paper ledger, or order surface changes."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution is "
                "still sparse. Skipped options and 13F because local PIT rows "
                "do not cover the canonical windows. Skipped nearby Companyfacts, "
                "FINRA/FTD, Form 4, post-earnings, Space, and SEC source-span "
                "retunes because they were just accepted/rejected or require "
                "forward replacement rows."
            ),
            "interpretation": (
                "Positive replay lead only; no production/shared policy was "
                "changed, so no backtest/production mismatch was introduced."
                if gate4["passed"]
                else (
                    "The broad low-beta residual momentum candidate source did "
                    "not clear Gate 4. Do not promote it or retune nearby beta/"
                    "correlation/residual-momentum thresholds on these frozen "
                    "windows without forward rows or a new orthogonal data source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else ";".join(gate4["failed_reasons"]),
            "next_retry_requires": [
                "closed forward replacement-value rows",
                "proof the hidden-beta field is incremental beyond broad OHLCV momentum",
                "shared default-off adapter and parity tests before promotion",
                "avoid beta/correlation/residual-threshold retunes on the same frozen sample",
            ],
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
            f"# {EXPERIMENT_ID} Broad Low-Beta Residual Momentum",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a replay-only/default-off broad OHLCV source admits top-1/day stocks with strong beta-adjusted residual momentum and low SPY beta/correlation.",
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM/news, or live/default behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


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


def _append_experiment_log(payload: dict[str, Any]) -> None:
    record = {
        key: payload.get(key)
        for key in [
            "experiment_id",
            "timestamp",
            "status",
            "lane",
            "hypothesis",
            "change_summary",
            "change_type",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "changed_variable",
            "prior_trial_count",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "parameters",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "prediction",
            "production_impact",
            "decision",
            "rejection_reason",
            "next_retry_requires",
            "anti_js",
        ]
    }
    record["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(TICKET_JSON),
    ]
    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as handle:
        json.dump(framework.base._safe(record), handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


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
    _append_experiment_log(payload)
    _write_manifest()


def _patch_modules() -> None:
    source.EXPERIMENT_ID = EXPERIMENT_ID
    source.STEM = STEM
    source.TRIAL_FAMILY = TRIAL_FAMILY
    source.CHANGED_VARIABLE = CHANGED_VARIABLE
    source.RULE_VERSION = RULE_VERSION
    source.OUT_DIR = OUT_DIR
    source.OUT_JSON = OUT_JSON
    source.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    source.AFTER_AGG_JSON = AFTER_AGG_JSON
    source.LOG_JSON = LOG_JSON
    source.TICKET_JSON = TICKET_JSON
    source.CARD_MD = CARD_MD
    source.ARTIFACT_MD = ARTIFACT_MD
    source.MANIFEST_JSON = MANIFEST_JSON
    source.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    source.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    source.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    source.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    source.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    source.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    source._candidate_rows_for_window = _candidate_rows_for_window
    source._patch_framework()


def main() -> int:
    _patch_modules()
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
    raise SystemExit(main())
