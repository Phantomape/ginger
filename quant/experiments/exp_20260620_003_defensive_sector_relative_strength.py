"""exp-20260620-003: defensive sector relative-strength scout.

Replay-only alpha search. The single decision hypothesis is that PIT OHLCV
relative strength in defensive sector ETFs (XLP/XLV/XLU) can identify
sector-matched liquid defensive stocks with better 10-trading-day continuation
when the tape is risk-averse.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from datetime import timedelta
from pathlib import Path
from typing import Any

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import exp_20260619_021_tlt_rate_relief_growth_leadership as template  # noqa: E402


framework = template.framework

EXPERIMENT_ID = "exp-20260620-003"
STEM = "defensive_sector_relative_strength"
TRIAL_FAMILY = "defensive_sector_relative_strength_candidate_pool"
TRIAL_VARIANT_ID = "defensive_sector_relative_strength_top1_next_open_10d_v1"
CHANGED_VARIABLE = "defensive_sector_relative_strength_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

DEFENSIVE_ETF_TICKERS = ("XLP", "XLV", "XLU")
MARKET_PROXY_TICKER = "SPY"
DEFENSIVE_SECTORS = {"Consumer Defensive", "Healthcare", "Utilities"}

MIN_DEFENSIVE_ETF_COUNT = 2
MIN_DEFENSIVE_RET20_EXCESS_SPY = 0.015
MIN_DEFENSIVE_RET5 = -0.025
MIN_AVG_DEFENSIVE_RET20_EXCESS_SPY = 0.025
MIN_SPY_RET20 = -0.12

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.00
MIN_RET60_EXCESS_SPY = 0.02
MIN_RET5 = -0.035
MIN_SIGNAL_RETURN = -0.04
MAX_SIGNAL_RETURN = 0.06
MIN_CLOSE_LOCATION = 0.50
MAX_REALIZED_VOL_20D = 0.08

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "macro_proxy_not_incremental",
        "window_regression",
        "accepted_comparator_not_beaten",
        "defensive_lag_concentration",
    ],
    "confidence_reason": (
        "The recent TLT/uranium and many SEC fields failed, while this uses a "
        "different free PIT OHLCV relation: defensive sector ETF breadth rather "
        "than duration, commodity, ownership, or Companyfacts ratios. Main risk "
        "is that defensive stocks lag the accepted compression/distribution "
        "comparators after next-open execution and costs."
    ),
    "recorded_at": "2026-06-20T02:08:01+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "uses_defensive_sector_etf_breadth": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing XLP/XLV/XLU/SPY OHLCV, failed defensive ETF breadth, "
            "missing defensive-sector candidate OHLCV, missing next open, or "
            "missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "defensive ETF breadth context, defensive-sector candidate gate, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: defensive sector ETF relative strength in XLP/XLV/XLU "
        "may identify lower-beta liquid defensive-stock continuation candidates "
        "during risk-averse tape, expanding the default-off paper candidate pool "
        "without SEC or LLM fields."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate warned on broad OHLCV momentum and sector-momentum "
            "families. The override declares a new evidence axis: PIT defensive "
            "sector ETF breadth from XLP/XLV/XLU with sector-matched stock "
            "candidates."
        ),
        "exp-20260607-019": (
            "Accepted volatility-relief stock leadership used VIXY compression. "
            "This run does not use VIXY and requires defensive sector ETF "
            "relative breadth plus sector membership."
        ),
        "exp-20260611-019": (
            "Rejected distribution-pressure low-beta defensive leadership. This "
            "run is not a low-beta screen inside distribution pressure; it uses "
            "sector ETF breadth and stock-level continuation."
        ),
        "exp-20260619-021": (
            "Rejected TLT rate-relief growth leadership. This run does not use "
            "duration/rate relief or growth leadership."
        ),
        "exp-20260620-001": (
            "Rejected uranium/nuclear theme beta. This run avoids fixed theme "
            "baskets and uses sector taxonomy plus defensive ETF breadth."
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
        "exp_20260620_003_defensive_sector_relative_strength.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=130)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(
        set(eligible_tickers) | set(DEFENSIVE_ETF_TICKERS) | {MARKET_PROXY_TICKER}
    )
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _defensive_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = framework.shadow._series(snapshot, MARKET_PROXY_TICKER)
    spy_idx = indices.get(MARKET_PROXY_TICKER, {}).get(signal_date)
    if spy_idx is None or spy_idx < 60:
        return None
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if spy_ret20 is None or spy_ret20 < MIN_SPY_RET20:
        return None

    passed: list[dict[str, Any]] = []
    for ticker in DEFENSIVE_ETF_TICKERS:
        rows = framework.shadow._series(snapshot, ticker)
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 60:
            continue
        ret20 = framework._ret(rows, idx, 20)
        ret5 = framework._ret(rows, idx, 5)
        close_location = framework._close_location(rows[idx])
        if ret20 is None or ret5 is None or close_location is None:
            continue
        ret20_excess_spy = ret20 - spy_ret20
        if ret20_excess_spy < MIN_DEFENSIVE_RET20_EXCESS_SPY:
            continue
        if ret5 < MIN_DEFENSIVE_RET5:
            continue
        passed.append(
            {
                "ticker": ticker,
                "ret20": _round(ret20, 6),
                "ret5": _round(ret5, 6),
                "ret20_excess_spy": _round(ret20_excess_spy, 6),
                "close_location": _round(close_location, 6),
            }
        )

    if len(passed) < MIN_DEFENSIVE_ETF_COUNT:
        return None
    avg_ret20_excess = sum(float(row["ret20_excess_spy"]) for row in passed) / len(passed)
    if avg_ret20_excess < MIN_AVG_DEFENSIVE_RET20_EXCESS_SPY:
        return None
    avg_ret5 = sum(float(row["ret5"]) for row in passed) / len(passed)
    return {
        "defensive_etf_tickers": list(DEFENSIVE_ETF_TICKERS),
        "passed_defensive_etfs": [row["ticker"] for row in passed],
        "passed_defensive_etf_count": len(passed),
        "spy_ret20": _round(spy_ret20, 6),
        "defensive_avg_ret20_excess_spy": _round(avg_ret20_excess, 6),
        "defensive_avg_ret5": _round(avg_ret5, 6),
        "defensive_details": passed,
        "defensive_context_known_at": "signal_date_ohlcv_close",
    }


def _candidate_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, MARKET_PROXY_TICKER)
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get(MARKET_PROXY_TICKER, {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if min(idx, spy_idx) < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx, 20)
    required = (
        signal_return,
        close_location,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    )
    if any(value is None for value in required):
        return None
    assert signal_return is not None and close_location is not None
    assert ret5 is not None and ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if ret5 < MIN_RET5:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    score = (
        0.65 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.25 * ret5
        + 0.30 * float(context["defensive_avg_ret20_excess_spy"])
        + 0.12 * close_location
        - 0.50 * realized_vol
        + 0.025 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "candidate_score": _round(score, 6),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret5": _round(ret5, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret60": _round(ret60, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    eligible_tickers: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(
        ticker
        for ticker in set(eligible_tickers) & set(snapshot)
        if ticker not in set(DEFENSIVE_ETF_TICKERS) | {MARKET_PROXY_TICKER}
        and (sector_entries.get(ticker, {}).get("sector") in DEFENSIVE_SECTORS)
    )
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_defensive_sector_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    context_sample: list[dict[str, Any]] = []
    for signal_date in window_dates:
        context = _defensive_context(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            scan["failed_defensive_context_days"] += 1
            continue
        scan["defensive_context_pass_days"] += 1
        if len(context_sample) < 5:
            context_sample.append({"date": signal_date, **context})
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            confirm = _candidate_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if confirm is None:
                scan["failed_candidate_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "DEFENSIVE_SECTOR_RELATIVE_STRENGTH_PAPER",
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "signal_date_ohlcv_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "same_ticker_ab_overlap": False,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_defensive_sector_etf_breadth": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **context,
                    **confirm,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_ret60_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(candidates)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    scan["context_sample"] = context_sample
    return candidates, {
        **dict(scan),
        "defensive_etf_tickers": list(DEFENSIVE_ETF_TICKERS),
        "defensive_sectors": sorted(DEFENSIVE_SECTORS),
    }


def _configure_template() -> None:
    template.EXPERIMENT_ID = EXPERIMENT_ID
    template.STEM = STEM
    template.TRIAL_FAMILY = TRIAL_FAMILY
    template.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    template.CHANGED_VARIABLE = CHANGED_VARIABLE
    template.RULE_VERSION = RULE_VERSION
    template.OWNER = OWNER
    template.OUT_DIR = OUT_DIR
    template.OUT_JSON = OUT_JSON
    template.LOG_JSON = LOG_JSON
    template.TICKET_JSON = TICKET_JSON
    template.CARD_MD = CARD_MD
    template.MANIFEST_JSON = MANIFEST_JSON
    template.EXPERIMENT_LOG = EXPERIMENT_LOG
    template.REGISTRY_JSON = REGISTRY_JSON
    template.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    template.HOLD_DAYS = HOLD_DAYS
    template.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    template.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    template.RATE_PROXY_TICKER = DEFENSIVE_ETF_TICKERS[0]
    template.GROWTH_PROXY_TICKER = DEFENSIVE_ETF_TICKERS[1]
    template.MARKET_PROXY_TICKER = MARKET_PROXY_TICKER
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._load_window_snapshot = _load_window_snapshot
    template._candidate_rows_for_window = _candidate_rows_for_window


def _finalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    target_summary = payload["target_trade_summary"]
    decision = (
        "positive_replay_lead_not_promoted_defensive_sector_relative_strength_candidate_pool"
        if gate4["passed"]
        else "rejected_defensive_sector_relative_strength_candidate_pool"
    )
    payload["decision"] = decision
    payload["gate4"]["decision"] = decision
    payload["mechanism_family"] = "production_visible_free_defensive_sector_ohlcv_candidate_pool"
    payload["new_evidence_type"] = "free_ohlcv_defensive_sector_etf_breadth"
    payload["nearby_prior_experiments"] = [
        "exp-20260607-019",
        "exp-20260611-019",
        "exp-20260619-021",
        "exp-20260620-001",
    ]
    payload["prior_trial_count"] = 0
    payload["multiple_testing_risk_bucket"] = "high"
    payload["backtest_protocol"]["cross_asset_context_source"] = _repo_rel(framework.WAREHOUSE)
    payload["backtest_protocol"]["defensive_etf_tickers"] = list(DEFENSIVE_ETF_TICKERS)
    payload["backtest_protocol"]["execution_model"] = (
        "XLP, XLV, XLU, SPY, and defensive-sector candidate stock features "
        "are computed from OHLCV rows with Date <= signal_date. Candidate "
        "stocks must have sector metadata in Consumer Defensive, Healthcare, "
        "or Utilities. Paper entry is the next available open with existing "
        "entry slippage; exit is the close 10 trading days after the signal "
        "with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "defensive_etf_tickers": list(DEFENSIVE_ETF_TICKERS),
        "defensive_sectors": sorted(DEFENSIVE_SECTORS),
        "min_defensive_etf_count": MIN_DEFENSIVE_ETF_COUNT,
        "min_defensive_ret20_excess_spy": MIN_DEFENSIVE_RET20_EXCESS_SPY,
        "min_defensive_ret5": MIN_DEFENSIVE_RET5,
        "min_avg_defensive_ret20_excess_spy": MIN_AVG_DEFENSIVE_RET20_EXCESS_SPY,
        "min_spy_ret20": MIN_SPY_RET20,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_ret5": MIN_RET5,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
    }
    payload["gate2"]["runtime_fields"] = [
        "XLP OHLCV Date/Open/High/Low/Close/Volume",
        "XLV OHLCV Date/Open/High/Low/Close/Volume",
        "XLU OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV Date/Open/High/Low/Close/Volume",
        "candidate OHLCV Date/Open/High/Low/Close/Volume",
        "candidate sector metadata",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    for coverage in payload["warehouse_coverage_by_window"].values():
        coverage["defensive_etf_tickers"] = list(DEFENSIVE_ETF_TICKERS)
    payload["interpretation"] = (
        "The defensive-sector relative-strength source cleared Gate 4 as a "
        "replay-only/default-off lead, but no production surface was promoted."
        if gate4["passed"]
        else (
            "The defensive-sector relative-strength source did not clear Gate "
            "4 (failed: "
            + (", ".join(gate4["failed_reasons"]) or "none")
            + "). Do not promote or tune this fixed defensive ETF breadth "
            "bundle on the same frozen windows."
        )
    )
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT defensive-flow evidence, such "
        "as sector fund-flow, earnings/cash-flow quality, or closed forward "
        "replacement-value rows. Do not sweep XLP/XLV/XLU breadth thresholds, "
        "sector lists, RS/close/volume/vol guards, top-N, hold, cooldown, or "
        "notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Gate 4 passed numerically, but this is replay-only because no "
            "shared daily/backtest helper exists."
            if gate4["passed"]
            else (
                "Rejected. Defensive ETF breadth plus sector-matched stock "
                "leadership did not add robust replacement value versus the "
                "accepted compression/distribution candidate-pool comparators "
                "after next-open execution, costs, cooldown, and concentration "
                "checks (failed: {}). The relation likely captures lagging "
                "defensive rotation rather than a distinct deployable "
                "continuation edge."
            ).format(", ".join(gate4["failed_reasons"]) or "none")
        ),
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
            "Do not retry by sweeping XLP/XLV/XLU breadth thresholds, defensive "
            "sector lists, RS/close/volume/volatility guards, top-N, hold days, "
            "cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": (
            "Need PIT defensive-sector flow/fundamental-quality evidence or "
            "closed forward replacement-value rows before revisiting defensive "
            "sector relative-strength leadership."
        ),
    }
    payload["related_files"] = [
        _repo_rel(THIS_FILE),
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Context days | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {ctx} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                ctx=scan.get("defensive_context_pass_days", 0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Defensive Sector Relative Strength",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                template.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                template.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                template.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                template.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
        "baseline_result_file": _repo_rel(template.BASELINE_RESULT_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": template.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": template.DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "defensive_context_pass_days": payload["context_scan_by_window"][label].get("defensive_context_pass_days"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
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
            _repo_rel(THIS_FILE),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(THIS_FILE): framework._sha256(THIS_FILE),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    template.base.persist_self_registered_result(
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
    _configure_template()
    payload = _finalize_payload(template._build_payload())
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
