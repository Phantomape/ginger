"""exp-20260621-003: factor-residual idiosyncratic leadership scout.

Replay-only alpha search. The single decision hypothesis is that liquid stocks
with positive 20-session leadership after PIT rolling residualization against
SPY and MSCI single-factor ETF reference returns can identify idiosyncratic
demand instead of generic market/style beta.

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

EXPERIMENT_ID = "exp-20260621-003"
STEM = "factor_residual_idiosyncratic_leadership"
TRIAL_FAMILY = "factor_residual_idiosyncratic_leadership_candidate_pool"
TRIAL_VARIANT_ID = "factor_residual_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "factor_residual_idiosyncratic_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_003_{STEM}.json"
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

MARKET_PROXY_TICKER = "SPY"
FACTOR_ETF_TICKERS = ("MTUM", "QUAL", "VLUE", "USMV", "SIZE")
REFERENCE_TICKERS = (MARKET_PROXY_TICKER, *FACTOR_ETF_TICKERS)

BETA_LOOKBACK_DAYS = 60
RESIDUAL_WINDOW_DAYS = 20
MIN_BETA_OBSERVATIONS = 45
MIN_RESIDUAL_OBSERVATIONS = 16
RIDGE_LAMBDA = 1e-5

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20 = 0.04
MAX_RET20 = 0.35
MIN_RET20_EXCESS_SPY = 0.015
MIN_RET60_EXCESS_SPY = 0.00
MIN_FACTOR_RESIDUAL_20D = 0.035
MIN_FACTOR_RESIDUAL_SHARE = 0.35
MAX_FACTOR_EXPLAINED_SHARE = 0.80
MAX_FACTOR_MODEL_R2 = 0.65
MAX_ABS_MARKET_BETA = 1.80
MIN_SIGNAL_RETURN = -0.03
MAX_SIGNAL_RETURN = 0.08
MIN_CLOSE_LOCATION = 0.50
MAX_REALIZED_VOL_20D = 0.13

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "generic_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "factor_reference_history_gap",
    ],
    "confidence_reason": (
        "exp-20260620-027 showed MTUM/QUAL/VLUE/USMV/SIZE are now available "
        "as PIT reference series and explain little of core residual alpha. "
        "This tests rolling factor-residual leadership rather than another "
        "SPY-residual or industry-correlation variant, but broad OHLCV "
        "continuation remains high multiple-testing risk."
    ),
    "recorded_at": "2026-06-21T02:09:09+00:00",
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
    "uses_factor_etf_reference_context": True,
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
            "missing SPY/factor ETF OHLCV, insufficient beta-fit history, "
            "missing candidate OHLCV, missing next open, or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "factor ETF reference context, PIT rolling beta fit, residual "
        "leadership gate, cooldown, next-open paper entry, 10-day exit, costs, "
        "and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: liquid stocks with strong 20-session price leadership "
        "that remains positive after rolling residualization against SPY and "
        "MTUM/QUAL/VLUE/USMV/SIZE factor ETF reference returns may capture "
        "idiosyncratic demand, expanding the default-off paper candidate pool "
        "without relying on generic momentum beta."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate blocked this as an idiosyncratic-leader near "
            "neighbor. The override records the new evidence axis: PIT "
            "MTUM/QUAL/VLUE/USMV/SIZE reference series from exp-20260620-027 "
            "and a rolling factor-residual field not used by prior SPY or "
            "industry/correlation residual tests."
        ),
        "exp-20260614-006": (
            "Rejected correlation-breakdown idiosyncratic leader. That run "
            "used industry/correlation context and failed old_thin/drawdown; "
            "this run uses factor ETF residualization instead."
        ),
        "exp-20260620-020": (
            "Measured core stack market/style beta using SPY/QQQ/IWM proxies; "
            "it was diagnostic and did not test a stock-level factor-residual "
            "candidate source."
        ),
        "exp-20260620-027": (
            "Built the new MTUM/QUAL/VLUE/USMV/SIZE reference surface used "
            "here; it did not change strategy behavior."
        ),
        "exp-20260621-002": (
            "Rejected SPY trend-down beta hedge. This run is candidate-pool "
            "selection, not a portfolio hedge or risk-allocation overlay."
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
        "exp_20260621_003_factor_residual_idiosyncratic_leadership.py"
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
    start = framework._parse_date(cfg["start"]) - timedelta(days=150)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | set(REFERENCE_TICKERS))
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


def _daily_return_by_date(rows: list[dict[str, Any]]) -> dict[str, float]:
    values: dict[str, float] = {}
    for idx in range(1, len(rows)):
        ret = framework._daily_return(rows, idx)
        if ret is not None and math.isfinite(ret):
            values[str(rows[idx]["Date"])] = float(ret)
    return values


def _factor_features_by_date(
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, list[float]]:
    returns = {
        ticker: _daily_return_by_date(framework.shadow._series(snapshot, ticker))
        for ticker in REFERENCE_TICKERS
        if ticker in snapshot
    }
    if set(REFERENCE_TICKERS) - set(returns):
        return {}
    dates = sorted(set(returns[MARKET_PROXY_TICKER]))
    features: dict[str, list[float]] = {}
    for day in dates:
        spy_ret = returns[MARKET_PROXY_TICKER].get(day)
        if spy_ret is None:
            continue
        row = [spy_ret]
        missing = False
        for ticker in FACTOR_ETF_TICKERS:
            factor_ret = returns[ticker].get(day)
            if factor_ret is None:
                missing = True
                break
            row.append(factor_ret - spy_ret)
        if not missing:
            features[day] = row
    return features


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    aug = [matrix[row][:] + [vector[row]] for row in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(aug[row][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_value = aug[col][col]
        for idx in range(col, size + 1):
            aug[col][idx] /= pivot_value
        for row in range(size):
            if row == col:
                continue
            factor = aug[row][col]
            if factor == 0.0:
                continue
            for idx in range(col, size + 1):
                aug[row][idx] -= factor * aug[col][idx]
    return [aug[row][size] for row in range(size)]


def _fit_factor_model(
    x_rows: list[list[float]],
    y_values: list[float],
) -> dict[str, Any] | None:
    if len(x_rows) < MIN_BETA_OBSERVATIONS or len(x_rows) != len(y_values):
        return None
    width = len(x_rows[0]) + 1
    xtx = [[0.0 for _ in range(width)] for _ in range(width)]
    xty = [0.0 for _ in range(width)]
    for x_row, y_value in zip(x_rows, y_values):
        values = [1.0, *x_row]
        for i in range(width):
            xty[i] += values[i] * y_value
            for j in range(width):
                xtx[i][j] += values[i] * values[j]
    for i in range(1, width):
        xtx[i][i] += RIDGE_LAMBDA
    coeffs = _solve_linear_system(xtx, xty)
    if coeffs is None:
        return None
    y_mean = sum(y_values) / len(y_values)
    sst = sum((value - y_mean) ** 2 for value in y_values)
    sse = 0.0
    for x_row, y_value in zip(x_rows, y_values):
        pred = coeffs[0] + sum(coeffs[idx + 1] * x_row[idx] for idx in range(len(x_row)))
        sse += (y_value - pred) ** 2
    r2 = 0.0 if sst <= 1e-12 else max(0.0, min(1.0, 1.0 - sse / sst))
    return {"coefficients": coeffs, "fit_r2": r2, "fit_observations": len(y_values)}


def _factor_residual_metrics(
    *,
    rows: list[dict[str, Any]],
    idx: int,
    factor_features: dict[str, list[float]],
) -> dict[str, Any] | None:
    fit_start = idx - RESIDUAL_WINDOW_DAYS - BETA_LOOKBACK_DAYS + 1
    fit_end = idx - RESIDUAL_WINDOW_DAYS
    if fit_start < 1:
        return None

    x_rows: list[list[float]] = []
    y_values: list[float] = []
    for row_idx in range(fit_start, fit_end + 1):
        day = str(rows[row_idx]["Date"])
        x_row = factor_features.get(day)
        y_value = framework._daily_return(rows, row_idx)
        if x_row is None or y_value is None:
            continue
        if not math.isfinite(y_value):
            continue
        x_rows.append(x_row)
        y_values.append(float(y_value))
    fit = _fit_factor_model(x_rows, y_values)
    if fit is None:
        return None

    coeffs = fit["coefficients"]
    actual_sum = 0.0
    factor_sums = [0.0 for _ in range(len(REFERENCE_TICKERS))]
    obs = 0
    for row_idx in range(idx - RESIDUAL_WINDOW_DAYS + 1, idx + 1):
        day = str(rows[row_idx]["Date"])
        x_row = factor_features.get(day)
        y_value = framework._daily_return(rows, row_idx)
        if x_row is None or y_value is None:
            continue
        actual_sum += float(y_value)
        for x_idx, value in enumerate(x_row):
            factor_sums[x_idx] += float(value)
        obs += 1
    if obs < MIN_RESIDUAL_OBSERVATIONS:
        return None
    predicted_sum = coeffs[0] * obs + sum(
        coeffs[idx + 1] * factor_sums[idx] for idx in range(len(factor_sums))
    )
    residual_sum = actual_sum - predicted_sum
    actual_abs = max(abs(actual_sum), 0.01)
    explained_share = abs(predicted_sum) / actual_abs
    residual_share = residual_sum / actual_abs
    return {
        "factor_residual_20d_sum": _round(residual_sum, 6),
        "factor_actual_20d_sum": _round(actual_sum, 6),
        "factor_predicted_20d_sum": _round(predicted_sum, 6),
        "factor_residual_share": _round(residual_share, 6),
        "factor_explained_share": _round(explained_share, 6),
        "factor_model_r2": _round(fit["fit_r2"], 6),
        "factor_model_fit_observations": fit["fit_observations"],
        "factor_residual_observations": obs,
        "factor_beta_market": _round(coeffs[1], 6),
        "factor_beta_momentum": _round(coeffs[2], 6),
        "factor_beta_quality": _round(coeffs[3], 6),
        "factor_beta_value": _round(coeffs[4], 6),
        "factor_beta_min_vol": _round(coeffs[5], 6),
        "factor_beta_size": _round(coeffs[6], 6),
    }


def _candidate_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    factor_features: dict[str, list[float]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, MARKET_PROXY_TICKER)
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get(MARKET_PROXY_TICKER, {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if min(idx, spy_idx) < BETA_LOOKBACK_DAYS + RESIDUAL_WINDOW_DAYS:
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
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx, 20)
    required = (
        signal_return,
        close_location,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    )
    if any(value is None for value in required):
        return None
    assert signal_return is not None and close_location is not None
    assert ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if ret20 < MIN_RET20 or ret20 > MAX_RET20:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    residual = _factor_residual_metrics(rows=rows, idx=idx, factor_features=factor_features)
    if residual is None:
        return None
    residual_20d = float(residual["factor_residual_20d_sum"] or 0.0)
    residual_share = float(residual["factor_residual_share"] or 0.0)
    explained_share = float(residual["factor_explained_share"] or 0.0)
    model_r2 = float(residual["factor_model_r2"] or 0.0)
    market_beta = abs(float(residual["factor_beta_market"] or 0.0))
    if residual_20d < MIN_FACTOR_RESIDUAL_20D:
        return None
    if residual_share < MIN_FACTOR_RESIDUAL_SHARE:
        return None
    if explained_share > MAX_FACTOR_EXPLAINED_SHARE:
        return None
    if model_r2 > MAX_FACTOR_MODEL_R2:
        return None
    if market_beta > MAX_ABS_MARKET_BETA:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    score = (
        1.20 * residual_20d
        + 0.40 * ret20_excess_spy
        + 0.18 * ret60_excess_spy
        + 0.08 * close_location
        - 0.18 * realized_vol
        - 0.08 * max(float(residual["factor_predicted_20d_sum"] or 0.0), 0.0)
        + 0.018 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "candidate_score": _round(score, 6),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret60": _round(ret60, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
        **residual,
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
    factor_features = _factor_features_by_date(snapshot)
    eligible = sorted(
        ticker
        for ticker in set(eligible_tickers) & set(snapshot)
        if ticker not in set(REFERENCE_TICKERS)
    )
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_universe_tickers"] = len(eligible)
    scan["factor_feature_dates"] = len(factor_features)
    candidates: list[dict[str, Any]] = []
    if not factor_features:
        scan["missing_factor_feature_surface"] = 1
        return candidates, dict(scan)

    factor_context_sample = [
        {"date": day, "features": [_round(value, 6) for value in factor_features[day]]}
        for day in sorted(factor_features)[:5]
    ]
    for signal_date in window_dates:
        if signal_date not in factor_features:
            scan["failed_factor_context_days"] += 1
            continue
        scan["factor_context_pass_days"] += 1
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            confirm = _candidate_confirmation(
                snapshot=snapshot,
                indices=indices,
                factor_features=factor_features,
                ticker=ticker,
                signal_date=signal_date,
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
                    "source": "FACTOR_RESIDUAL_IDIOSYNCRATIC_LEADERSHIP_PAPER",
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "signal_date_ohlcv_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "same_ticker_ab_overlap": False,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_factor_etf_reference_context": True,
                    "factor_reference_tickers": list(REFERENCE_TICKERS),
                    "uses_llm": False,
                    "trade_enabled": False,
                    **confirm,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["factor_residual_20d_sum"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(candidates)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    scan["factor_context_sample"] = factor_context_sample
    return candidates, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "market_proxy_ticker": MARKET_PROXY_TICKER,
        "factor_etf_tickers": list(FACTOR_ETF_TICKERS),
        "beta_lookback_days": BETA_LOOKBACK_DAYS,
        "residual_window_days": RESIDUAL_WINDOW_DAYS,
        "min_factor_residual_20d": MIN_FACTOR_RESIDUAL_20D,
        "min_factor_residual_share": MIN_FACTOR_RESIDUAL_SHARE,
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
    template.RATE_PROXY_TICKER = FACTOR_ETF_TICKERS[0]
    template.GROWTH_PROXY_TICKER = FACTOR_ETF_TICKERS[1]
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
    missing_factor_surface_windows = [
        label
        for label in framework.WINDOWS
        if not payload["context_scan_by_window"][label].get("factor_feature_dates", 0)
    ]
    factor_surface_blocked = bool(missing_factor_surface_windows)
    decision = (
        "blocked_factor_residual_reference_surface_missing"
        if factor_surface_blocked
        else
        "positive_replay_lead_not_promoted_factor_residual_idiosyncratic_leadership"
        if gate4["passed"]
        else "rejected_factor_residual_idiosyncratic_leadership_candidate_pool"
    )
    if factor_surface_blocked:
        payload["status"] = "blocked"
    payload["decision"] = decision
    payload["gate4"]["decision"] = decision
    if factor_surface_blocked and "factor_reference_history_gap" not in payload["gate4"]["failed_reasons"]:
        payload["gate4"]["failed_reasons"].insert(0, "factor_reference_history_gap")
    payload["mechanism_family"] = "production_visible_free_factor_residual_ohlcv_candidate_pool"
    payload["new_evidence_type"] = "free_factor_etf_style_residual_reference_series"
    payload["nearby_prior_experiments"] = [
        "exp-20260614-006",
        "exp-20260620-020",
        "exp-20260620-023",
        "exp-20260620-027",
        "exp-20260621-002",
    ]
    payload["prior_trial_count"] = 0
    payload["multiple_testing_risk_bucket"] = "high"
    payload["backtest_protocol"]["cross_asset_context_source"] = _repo_rel(framework.WAREHOUSE)
    payload["backtest_protocol"]["factor_reference_tickers"] = list(REFERENCE_TICKERS)
    payload["backtest_protocol"]["execution_model"] = (
        "SPY, MTUM, QUAL, VLUE, USMV, SIZE, and candidate stock features are "
        "computed from OHLCV rows with Date <= signal_date. Rolling factor "
        "betas are fit on the 60 trading-day period ending 20 sessions before "
        "signal date; the 20-day residual leadership window ends at signal "
        "date. Paper entry is the next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "market_proxy_ticker": MARKET_PROXY_TICKER,
        "factor_etf_tickers": list(FACTOR_ETF_TICKERS),
        "beta_lookback_days": BETA_LOOKBACK_DAYS,
        "residual_window_days": RESIDUAL_WINDOW_DAYS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "min_residual_observations": MIN_RESIDUAL_OBSERVATIONS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20": MIN_RET20,
        "max_ret20": MAX_RET20,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_factor_residual_20d": MIN_FACTOR_RESIDUAL_20D,
        "min_factor_residual_share": MIN_FACTOR_RESIDUAL_SHARE,
        "max_factor_explained_share": MAX_FACTOR_EXPLAINED_SHARE,
        "max_factor_model_r2": MAX_FACTOR_MODEL_R2,
        "max_abs_market_beta": MAX_ABS_MARKET_BETA,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
    }
    payload["gate2"]["runtime_fields"] = [
        "SPY OHLCV Date/Open/High/Low/Close/Volume",
        "MTUM OHLCV Date/Open/High/Low/Close/Volume",
        "QUAL OHLCV Date/Open/High/Low/Close/Volume",
        "VLUE OHLCV Date/Open/High/Low/Close/Volume",
        "USMV OHLCV Date/Open/High/Low/Close/Volume",
        "SIZE OHLCV Date/Open/High/Low/Close/Volume",
        "candidate OHLCV Date/Open/High/Low/Close/Volume",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["factor_reference_coverage_by_window"] = {
        label: {
            "factor_feature_dates": payload["context_scan_by_window"][label].get(
                "factor_feature_dates", 0
            ),
            "missing_factor_feature_surface": bool(
                payload["context_scan_by_window"][label].get("missing_factor_feature_surface")
            ),
        }
        for label in framework.WINDOWS
    }
    if factor_surface_blocked:
        payload["gate2"]["passed"] = False
        payload["gate2"]["blocking_item"] = (
            "warehouse_main.sqlite has SPY but lacks MTUM/QUAL/VLUE/USMV/SIZE "
            "OHLCV rows across the canonical windows; exp-20260620-027's "
            "factor_etf_daily.json is a diagnostic sidecar, not a production-"
            "visible shared OHLCV surface."
        )
    for coverage in payload["warehouse_coverage_by_window"].values():
        coverage["factor_reference_tickers"] = list(REFERENCE_TICKERS)
    for label, coverage in payload["warehouse_coverage_by_window"].items():
        factor_surface_present = bool(
            payload["context_scan_by_window"][label].get("factor_feature_dates", 0)
        )
        coverage["factor_reference_present"] = {
            ticker: factor_surface_present for ticker in REFERENCE_TICKERS
        }
    payload["interpretation"] = (
        "The factor-residual idiosyncratic leadership scout is blocked at Gate "
        "2: MTUM/QUAL/VLUE/USMV/SIZE reference rows are absent from the main "
        "production-visible OHLCV warehouse, so no trustworthy factor-residual "
        "candidate source can be evaluated."
        if factor_surface_blocked
        else
        "The factor-residual idiosyncratic leadership source cleared Gate 4 as "
        "a replay-only/default-off lead, but no production surface was promoted."
        if gate4["passed"]
        else (
            "The factor-residual idiosyncratic leadership source did not clear "
            "Gate 4 (failed: "
            + (", ".join(gate4["failed_reasons"]) or "none")
            + "). Do not promote or tune this fixed factor-residual OHLCV "
            "bundle on the same frozen windows."
        )
    )
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT flow, ownership, borrow/options, "
        "or closed forward replacement-value evidence. Do not sweep factor ETF "
        "lists, beta lookbacks, residual thresholds, RS/close/volume/volatility "
        "guards, top-N, hold, cooldown, or notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Blocked at Gate 2. The alpha idea required production-visible PIT "
            "MTUM/QUAL/VLUE/USMV/SIZE reference rows, but warehouse_main.sqlite "
            "contains no rows for those tickers in the canonical windows. Using "
            "the exp-20260620-027 sidecar would create a replay-only data path "
            "that the production/backtest parity contract does not support."
            if factor_surface_blocked
            else
            "Gate 4 passed numerically, but this is replay-only because no "
            "shared daily/backtest helper exists."
            if gate4["passed"]
            else (
                "Rejected. Factor-residual leadership did not add robust "
                "replacement value versus accepted compression/distribution "
                "candidate-pool comparators after next-open execution, costs, "
                "cooldown, and concentration checks (failed: {}). The relation "
                "likely still relabels crowded recent-winner demand or misses "
                "old_thin factor behavior rather than creating an independent "
                "candidate-pool edge."
            ).format(", ".join(gate4["failed_reasons"]) or "none")
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades; factor surface "
            "blocked windows: {}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                target_summary["total_trade_count"],
                ", ".join(missing_factor_surface_windows) or "none",
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping factor ETF lists, beta lookbacks, residual "
            "thresholds, factor share/R2 caps, RS/close/volume/volatility "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
        ),
        "new_evidence_required": (
            "Need PIT flow, ownership, borrow/options, event-quality, or closed "
            "forward replacement-value evidence before revisiting broad "
            "factor-residual leadership."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Factor days | Raw | Trades |",
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
                ctx=scan.get("factor_context_pass_days", 0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Factor Residual Idiosyncratic Leadership",
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
                "factor_context_pass_days": payload["context_scan_by_window"][label].get("factor_context_pass_days"),
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
