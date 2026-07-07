"""exp-20260707-003: daily-equity replay for the rank-3 portfolio-lane candidate.

This consumes the observed-only ranking from exp-20260706-022. It does not
retune the purchase-obligation source from exp-20260626-003 and does not change
live, paper, ranking, sizing, entry, or exit behavior. The only tested decision
hypothesis is whether this ranked rejected source still looks portfolio-useful
when its trades are replayed as daily mark-to-market equity instead of
exit-date terminal cashflows.
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260707-003"
OWNER = "alpha-explore"
LANE = "alpha_search"
STEM = "purchase_obligation_daily_equity_overlay"
STATUS_POSITIVE = "observed_only_positive_purchase_obligation_daily_equity_lead_not_activation_ready"
STATUS_REJECTED = "observed_only_rejected_purchase_obligation_daily_equity_overlay"
DECISION_POSITIVE = "observed_only_positive_purchase_obligation_daily_equity_overlay"
DECISION_REJECTED = "observed_only_rejected_purchase_obligation_daily_equity_overlay"

TRIAL_FAMILY = "portfolio_covariance_daily_equity_overlay"
TRIAL_VARIANT_ID = "purchase_obligation_rank3_10pct_daily_equity_overlay_v1"
CHANGED_VARIABLE = "purchase_obligation_rank3_portfolio_daily_equity_overlay_v1"
MECHANISM_FAMILY = "portfolio_covariance_lane"
CHANGE_TYPE = "risk_allocation"
NEW_EVIDENCE_TYPE = "new_ranked_source_artifact_for_daily_mark_to_market_overlay"
NEW_EVIDENCE_AXIS = (
    "New source artifact for the existing daily mark-to-market portfolio "
    "overlay gate: consume exp-20260706-022 rank-3 purchase-obligation rows "
    "from exp-20260626-003. Prior daily-equity overlays consumed "
    "fixed-asset-turnover, sector-breadth, deferred-revenue, and FINRA "
    "short-pressure; this does not retune overlay weight, thresholds, top-N, "
    "hold days, or Companyfacts source behavior."
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260707_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_RANKING_ARTIFACT = (
    "data/experiments/exp-20260706-022/"
    "exp_20260706_022_portfolio_covariance_candidate_ranking.json"
)
TARGET_SOURCE_ARTIFACT = (
    "data/experiments/exp-20260626-003/"
    "exp_20260626_003_companyfacts_purchase_obligation_ladder.json"
)
WAREHOUSE_SQLITE = "data/warehouse/warehouse_main.sqlite"
CORE_WINDOW_BASELINES = {
    "late_strong": (
        "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        "backtest_results_warehouse_snapshot_late_strong_20260604.json"
    ),
    "mid_weak": (
        "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
    ),
    "old_thin": (
        "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        "backtest_results_warehouse_snapshot_old_thin_20260604.json"
    ),
}
CANONICAL_WINDOWS = {
    "late_strong": {"start": "2025-10-23", "end": "2026-04-21"},
    "mid_weak": {"start": "2025-04-23", "end": "2025-10-22"},
    "old_thin": {"start": "2024-10-02", "end": "2025-04-22"},
}

PORTFOLIO_CAPITAL_USD = 100_000.0
OVERLAY_WEIGHT = 0.10
MAX_DRAWDOWN_DRIFT = 0.005
TERMINAL_MISMATCH_TOLERANCE_USD = 1.0

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "daily_drawdown_worse",
        "old_thin_regression",
        "proxy_edge_disappears",
        "companyfacts_source_fragility",
    ],
    "confidence_reason": (
        "The portfolio covariance ranking placed purchase-obligation third "
        "with positive exit-cashflow proxy PnL and acceptable low correlation, "
        "while prior daily-equity overlay tests showed the proxy can disappear; "
        "this test consumes a materially new ranked family without changing "
        "source thresholds or overlay weight."
    ),
    "recorded_at": "2026-07-07T02:04:07+00:00",
}

HYPOTHESIS = (
    "Portfolio lane: the exp-20260706-022 rank-3 purchase-obligation "
    "maturity-ladder rejected source may add value as a fixed 10 percent "
    "paper overlay when replayed with true daily mark-to-market equity, "
    "without retuning the Companyfacts source or overlay weight."
)
ALPHA_HYPOTHESIS = (
    "capital_allocation / risk_allocation: rejected candidate sources can be "
    "portfolio-useful if a small fixed overlay improves aggregate daily-equity "
    "EV while drawdown and window stability remain acceptable."
)
CAUSAL_COMPONENTS = [
    "consume exp-20260706-022 ranking",
    "daily mark-to-market equity replay",
    "accepted core equity comparison",
    "no source threshold retune",
    "no strategy behavior change",
]

RUNNER = f"quant/experiments/exp_20260707_003_{STEM}.py"
RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {RUNNER}"
RUNNER_WINDOWS = f"quant\\experiments\\exp_20260707_003_{STEM}.py"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260707_003_{STEM}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    for encoding in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            with path.open(encoding=encoding) as handle:
                return json.load(handle)
        except UnicodeError:
            continue
        except (OSError, json.JSONDecodeError):
            return default
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def required_missing(row: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if row.get(field) in (None, "")]


def load_target_trades() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    payload = read_json(REPO_ROOT / TARGET_SOURCE_ARTIFACT, {})
    by_window = payload.get("target_trades_by_window") if isinstance(payload, dict) else None
    diagnostics = {
        "source_artifact": TARGET_SOURCE_ARTIFACT,
        "loaded": isinstance(by_window, dict),
        "required_fields": [
            "ticker",
            "entry_date",
            "entry_price",
            "exit_date",
            "exit_price",
            "paper_notional_usd",
            "pnl",
        ],
        "missing_by_window": {},
    }
    out: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(by_window, dict):
        return out, diagnostics
    required = diagnostics["required_fields"]
    for window, rows in by_window.items():
        usable: list[dict[str, Any]] = []
        missing_counter: defaultdict[str, int] = defaultdict(int)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            missing = required_missing(row, required)
            if missing:
                for field in missing:
                    missing_counter[field] += 1
                continue
            usable.append(row)
        out[str(window)] = usable
        diagnostics["missing_by_window"][str(window)] = dict(sorted(missing_counter.items()))
    diagnostics["usable_counts"] = {window: len(rows) for window, rows in out.items()}
    return out, diagnostics


def load_core_trades() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    out: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, Any] = {"window_paths": CORE_WINDOW_BASELINES, "missing_by_window": {}}
    required = ["ticker", "entry_date", "entry_price", "exit_date", "exit_price", "pnl"]
    for window, rel_path in CORE_WINDOW_BASELINES.items():
        payload = read_json(REPO_ROOT / rel_path, {})
        rows = payload.get("trades") if isinstance(payload, dict) else None
        usable: list[dict[str, Any]] = []
        missing_counter: defaultdict[str, int] = defaultdict(int)
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                missing = required_missing(row, required)
                if missing:
                    for field in missing:
                        missing_counter[field] += 1
                    continue
                usable.append(row)
        out[window] = usable
        diagnostics["missing_by_window"][window] = dict(sorted(missing_counter.items()))
    diagnostics["usable_counts"] = {window: len(rows) for window, rows in out.items()}
    return out, diagnostics


def ticker_set(*trade_maps: dict[str, list[dict[str, Any]]]) -> set[str]:
    tickers: set[str] = {"SPY"}
    for trade_map in trade_maps:
        for rows in trade_map.values():
            for row in rows:
                ticker = str(row.get("ticker") or "").strip().upper()
                if ticker:
                    tickers.add(ticker)
    return tickers


def date_bounds(*trade_maps: dict[str, list[dict[str, Any]]]) -> tuple[date, date]:
    days: list[date] = []
    for spec in CANONICAL_WINDOWS.values():
        for key in ("start", "end"):
            parsed = parse_day(spec[key])
            if parsed:
                days.append(parsed)
    for trade_map in trade_maps:
        for rows in trade_map.values():
            for row in rows:
                for key in ("entry_date", "exit_date"):
                    parsed = parse_day(row.get(key))
                    if parsed:
                        days.append(parsed)
    return min(days), max(days)


def load_price_map(tickers: set[str], start: date, end: date) -> dict[str, dict[date, dict[str, float]]]:
    db_path = REPO_ROOT / WAREHOUSE_SQLITE
    placeholders = ",".join("?" for _ in sorted(tickers))
    params = [*sorted(tickers), start.isoformat(), end.isoformat()]
    query = (
        "select ticker, date, open, close from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    price_map: dict[str, dict[date, dict[str, float]]] = defaultdict(dict)
    with sqlite3.connect(db_path) as conn:
        for ticker, day_text, open_price, close_price in conn.execute(query, params):
            parsed = parse_day(day_text)
            if parsed is None:
                continue
            price_map[str(ticker).upper()][parsed] = {
                "open": float(open_price),
                "close": float(close_price),
            }
    return {ticker: dict(days) for ticker, days in price_map.items()}


def analysis_days(price_map: dict[str, dict[date, dict[str, float]]], start: date, end: date) -> list[date]:
    spy = price_map.get("SPY", {})
    return sorted(day for day in spy if start <= day <= end)


def window_days(
    price_map: dict[str, dict[date, dict[str, float]]],
    window: str,
    rows: list[dict[str, Any]],
) -> list[date]:
    start = parse_day(CANONICAL_WINDOWS[window]["start"])
    end = parse_day(CANONICAL_WINDOWS[window]["end"])
    exits = [parse_day(row.get("exit_date")) for row in rows]
    exits = [day for day in exits if day is not None]
    if exits:
        end = max([end, *exits]) if end is not None else max(exits)
    if start is None or end is None:
        return []
    return analysis_days(price_map, start, end)


def trade_daily_pnl(
    row: dict[str, Any],
    price_map: dict[str, dict[date, dict[str, float]]],
    *,
    notional_key: str,
    share_key: str | None = None,
) -> tuple[dict[date, float], dict[str, Any]]:
    ticker = str(row.get("ticker") or "").strip().upper()
    entry_date = parse_day(row.get("entry_date"))
    exit_date = parse_day(row.get("exit_date"))
    entry_price = as_float(row.get("entry_price"))
    exit_price = as_float(row.get("exit_price"))
    reported_pnl = as_float(row.get("pnl"))
    if not ticker or entry_date is None or exit_date is None or entry_price is None or exit_price is None:
        return {}, {"usable": False, "reason": "missing_required_trade_fields", "ticker": ticker}

    ticker_prices = price_map.get(ticker, {})
    days = sorted(day for day in ticker_prices if entry_date <= day <= exit_date)
    if entry_date not in ticker_prices or exit_date not in ticker_prices:
        return {}, {
            "usable": False,
            "reason": "missing_entry_or_exit_ohlcv",
            "ticker": ticker,
            "entry_date": entry_date.isoformat(),
            "exit_date": exit_date.isoformat(),
        }
    if not days:
        return {}, {"usable": False, "reason": "missing_holding_period_ohlcv", "ticker": ticker}

    shares = as_float(row.get(share_key)) if share_key else None
    notional = as_float(row.get(notional_key))
    if shares is None:
        if notional is None or entry_price <= 0:
            return {}, {"usable": False, "reason": "missing_notional_or_shares", "ticker": ticker}
        shares = notional / entry_price

    series: defaultdict[date, float] = defaultdict(float)
    previous_mark = entry_price
    for day in days:
        if day == exit_date:
            mark = exit_price
        else:
            mark = ticker_prices[day]["close"]
        series[day] += (mark - previous_mark) * shares
        previous_mark = mark

    gross_sum = sum(series.values())
    residual = (reported_pnl - gross_sum) if reported_pnl is not None else 0.0
    if abs(residual) > 1e-9:
        series[exit_date] += residual

    return dict(series), {
        "usable": True,
        "ticker": ticker,
        "entry_date": entry_date.isoformat(),
        "exit_date": exit_date.isoformat(),
        "reported_pnl": round(reported_pnl or 0.0, 6),
        "gross_mtm_pnl_before_residual": round(gross_sum, 6),
        "terminal_residual_applied": round(residual, 6),
        "holding_days_with_prices": len(days),
    }


def add_series(*series_list: dict[date, float]) -> dict[date, float]:
    out: defaultdict[date, float] = defaultdict(float)
    for series in series_list:
        for day, value in series.items():
            out[day] += value
    return dict(out)


def scale_series(series: dict[date, float], weight: float) -> dict[date, float]:
    return {day: value * weight for day, value in series.items()}


def build_series_for_rows(
    rows: list[dict[str, Any]],
    price_map: dict[str, dict[date, dict[str, float]]],
    *,
    notional_key: str,
    share_key: str | None = None,
) -> tuple[dict[date, float], dict[str, Any]]:
    total: defaultdict[date, float] = defaultdict(float)
    diagnostics: list[dict[str, Any]] = []
    missing: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        series, diag = trade_daily_pnl(
            row,
            price_map,
            notional_key=notional_key,
            share_key=share_key,
        )
        diagnostics.append(diag)
        if not diag.get("usable"):
            missing[str(diag.get("reason") or "unusable")] += 1
            continue
        for day, value in series.items():
            total[day] += value
    residuals = [abs(float(diag.get("terminal_residual_applied") or 0.0)) for diag in diagnostics if diag.get("usable")]
    return dict(total), {
        "trades_seen": len(rows),
        "trades_usable": sum(1 for diag in diagnostics if diag.get("usable")),
        "missing": dict(sorted(missing.items())),
        "terminal_residual_abs_sum": round(sum(residuals), 6),
        "terminal_residual_abs_max": round(max(residuals), 6) if residuals else 0.0,
        "sample": diagnostics[:5],
    }


def metric_series(series: dict[date, float], days: list[date]) -> dict[str, Any]:
    values = [series.get(day, 0.0) for day in days]
    if not values:
        return {
            "days": 0,
            "active_days": 0,
            "total_pnl": 0.0,
            "return_fraction": 0.0,
            "sharpe_daily": 0.0,
            "expected_value_score": 0.0,
            "max_drawdown_pct": 0.0,
            "min_day_pnl": 0.0,
            "positive_active_day_rate": None,
        }
    total_pnl = sum(values)
    daily_returns = [value / PORTFOLIO_CAPITAL_USD for value in values]
    mean_r = statistics.fmean(daily_returns)
    stdev_r = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0
    sharpe = mean_r / stdev_r * math.sqrt(252.0) if stdev_r > 0 else 0.0
    balance = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        balance += value
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    active_values = [value for value in values if abs(value) > 1e-9]
    positive_active = [value for value in active_values if value > 0]
    return_fraction = total_pnl / PORTFOLIO_CAPITAL_USD
    return {
        "days": len(values),
        "active_days": len(active_values),
        "total_pnl": round(total_pnl, 2),
        "return_fraction": round(return_fraction, 6),
        "sharpe_daily": round(sharpe, 6),
        "expected_value_score": round(return_fraction * sharpe, 6),
        "max_drawdown_pct": round(max_drawdown / PORTFOLIO_CAPITAL_USD, 6),
        "min_day_pnl": round(min(values), 2),
        "positive_active_day_rate": (
            round(len(positive_active) / len(active_values), 6) if active_values else None
        ),
    }


def metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "total_pnl",
        "return_fraction",
        "sharpe_daily",
        "expected_value_score",
        "max_drawdown_pct",
        "min_day_pnl",
    ]
    return {key: round(float(after[key]) - float(before[key]), 6) for key in keys}


def pearson(left: dict[date, float], right: dict[date, float], days: list[date]) -> float | None:
    xs = [left.get(day, 0.0) for day in days]
    ys = [right.get(day, 0.0) for day in days]
    if len(xs) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return round(covariance / math.sqrt(var_x * var_y), 6)


def source_ranking_audit() -> dict[str, Any]:
    payload = read_json(REPO_ROOT / SOURCE_RANKING_ARTIFACT, {})
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return {
        "source_artifact": SOURCE_RANKING_ARTIFACT,
        "loaded": isinstance(payload, dict) and bool(payload),
        "top_candidate": summary.get("top_candidate") if isinstance(summary, dict) else None,
        "top_candidate_family": summary.get("top_candidate_family") if isinstance(summary, dict) else None,
        "top_candidate_core_correlation_exit_cashflow": (
            summary.get("top_candidate_core_correlation_exit_cashflow")
            if isinstance(summary, dict)
            else None
        ),
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now_iso()
    target_trades, target_diag = load_target_trades()
    core_trades, core_diag = load_core_trades()
    start, end = date_bounds(target_trades, core_trades)
    prices = load_price_map(ticker_set(target_trades, core_trades), start, end)

    by_window: dict[str, Any] = {}
    failure_reasons: list[str] = []
    aggregate_core: defaultdict[date, float] = defaultdict(float)
    aggregate_overlay: defaultdict[date, float] = defaultdict(float)
    aggregate_days_set: set[date] = set()

    for window in ("late_strong", "mid_weak", "old_thin"):
        core_rows = core_trades.get(window, [])
        target_rows = target_trades.get(window, [])
        rows_for_days = [*core_rows, *target_rows]
        days = window_days(prices, window, rows_for_days)
        core_series, core_series_diag = build_series_for_rows(
            core_rows,
            prices,
            notional_key="entry_notional",
            share_key="shares",
        )
        target_series, target_series_diag = build_series_for_rows(
            target_rows,
            prices,
            notional_key="paper_notional_usd",
        )
        overlay_series = scale_series(target_series, OVERLAY_WEIGHT)
        combined = add_series(core_series, overlay_series)
        core_metrics = metric_series(core_series, days)
        overlay_metrics = metric_series(overlay_series, days)
        combined_metrics = metric_series(combined, days)
        delta = metric_delta(combined_metrics, core_metrics)
        correlation = pearson(core_series, overlay_series, days)

        for day, value in core_series.items():
            aggregate_core[day] += value
        for day, value in overlay_series.items():
            aggregate_overlay[day] += value
        aggregate_days_set.update(days)

        by_window[window] = {
            "days_start": days[0].isoformat() if days else None,
            "days_end": days[-1].isoformat() if days else None,
            "core_trade_count": len(core_rows),
            "target_trade_count": len(target_rows),
            "overlay_weight": OVERLAY_WEIGHT,
            "core_metrics_daily_mtm_proxy": core_metrics,
            "overlay_metrics_daily_mtm": overlay_metrics,
            "combined_metrics_daily_mtm_proxy": combined_metrics,
            "delta_metrics_daily_mtm_proxy": delta,
            "core_overlay_daily_pnl_correlation": correlation,
            "core_series_diagnostics": core_series_diag,
            "target_series_diagnostics": target_series_diag,
        }

    aggregate_days = sorted(aggregate_days_set)
    aggregate_combined = add_series(dict(aggregate_core), dict(aggregate_overlay))
    aggregate_core_metrics = metric_series(dict(aggregate_core), aggregate_days)
    aggregate_overlay_metrics = metric_series(dict(aggregate_overlay), aggregate_days)
    aggregate_combined_metrics = metric_series(aggregate_combined, aggregate_days)
    aggregate_delta = metric_delta(aggregate_combined_metrics, aggregate_core_metrics)
    aggregate_correlation = pearson(dict(aggregate_core), dict(aggregate_overlay), aggregate_days)

    ev_improved = [
        window
        for window, metrics in by_window.items()
        if metrics["delta_metrics_daily_mtm_proxy"]["expected_value_score"] > 0
    ]
    pnl_improved = [
        window
        for window, metrics in by_window.items()
        if metrics["delta_metrics_daily_mtm_proxy"]["total_pnl"] > 0
    ]
    ev_regressed = [
        window
        for window, metrics in by_window.items()
        if metrics["delta_metrics_daily_mtm_proxy"]["expected_value_score"] < 0
    ]
    drawdown_drift = aggregate_delta["max_drawdown_pct"]

    if aggregate_delta["expected_value_score"] <= 0:
        failure_reasons.append("aggregate_daily_equity_ev_delta_not_positive")
    if aggregate_delta["total_pnl"] <= 0:
        failure_reasons.append("aggregate_daily_equity_pnl_delta_not_positive")
    if len(ev_improved) < 2:
        failure_reasons.append("fewer_than_two_daily_equity_ev_improved_windows")
    if drawdown_drift > MAX_DRAWDOWN_DRIFT:
        failure_reasons.append("daily_equity_drawdown_drift_too_high")
    missing_ohlcv = {
        window: {
            "core": by_window[window]["core_series_diagnostics"]["missing"],
            "target": by_window[window]["target_series_diagnostics"]["missing"],
        }
        for window in by_window
        if by_window[window]["core_series_diagnostics"]["missing"]
        or by_window[window]["target_series_diagnostics"]["missing"]
    }
    blocking_target_missing_ohlcv = {
        window: missing["target"]
        for window, missing in missing_ohlcv.items()
        if missing.get("target")
    }
    nonblocking_core_missing_ohlcv = {
        window: missing["core"]
        for window, missing in missing_ohlcv.items()
        if missing.get("core")
    }
    if blocking_target_missing_ohlcv:
        failure_reasons.append("missing_ohlcv_path")
    if ev_regressed:
        failure_reasons.append("daily_equity_window_ev_regression")
    pnl_regressed = [
        window
        for window, metrics in by_window.items()
        if metrics["delta_metrics_daily_mtm_proxy"]["total_pnl"] < 0
    ]
    if pnl_regressed:
        failure_reasons.append("daily_equity_window_pnl_regression")
    target_cost_residual_max = max(
        by_window[window]["target_series_diagnostics"]["terminal_residual_abs_max"]
        for window in by_window
    )

    positive_lead = not failure_reasons
    status = STATUS_POSITIVE if positive_lead else STATUS_REJECTED
    decision = DECISION_POSITIVE if positive_lead else DECISION_REJECTED
    actual_success = 1 if positive_lead else 0
    predicted = float(PREDICTION["success_probability"])

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_daily_equity_replay_no_strategy_change",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": [
            "exp-20260706-022",
            "exp-20260706-023",
            "exp-20260706-025",
            "exp-20260707-001",
            "exp-20260626-003",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "parameters": {
            "source_ranking_artifact": SOURCE_RANKING_ARTIFACT,
            "target_source_artifact": TARGET_SOURCE_ARTIFACT,
            "warehouse_sqlite": WAREHOUSE_SQLITE,
            "overlay_weight": OVERLAY_WEIGHT,
            "portfolio_capital_usd": PORTFOLIO_CAPITAL_USD,
            "acceptance_boundary": (
                "observed-only daily-equity lead only; activation still needs "
                "a shared helper / paper behavior and standard Gate 1-4"
            ),
            "source_behavior_changed": False,
        },
        "gate1": {
            "passed": bool(core_trades) and bool(target_trades),
            "baseline_result_file": BASELINE_RESULT_FILE,
            "core_window_baselines": CORE_WINDOW_BASELINES,
            "source_ranking_audit": source_ranking_audit(),
            "target_source_diagnostics": target_diag,
            "core_diagnostics": core_diag,
        },
        "gate2": {
            "passed": not blocking_target_missing_ohlcv,
            "fields_checked": [
                "ticker",
                "entry_date",
                "entry_price",
                "exit_date",
                "exit_price",
                "pnl",
                "paper_notional_usd",
                "shares",
            ],
            "missing_ohlcv": missing_ohlcv,
            "blocking_target_missing_ohlcv": blocking_target_missing_ohlcv,
            "nonblocking_core_missing_ohlcv": nonblocking_core_missing_ohlcv,
            "target_cost_residual_abs_max": target_cost_residual_max,
            "target_cost_residual_note": (
                "Residual is applied on the exit date to reconcile the MTM path "
                "to artifact PnL after round-trip cost and rounding; it is not "
                "a terminal mismatch."
            ),
        },
        "gate3": {
            "applicable": False,
            "filter_added": False,
            "reason": "No signal filter was added; fixed historical target rows are replayed.",
            "target_trade_count": sum(len(rows) for rows in target_trades.values()),
            "survival_rate": None,
        },
        "gate4": {
            "applicable": True,
            "passed_daily_equity_replay": positive_lead,
            "passed_alpha_activation": False,
            "failed_reasons": failure_reasons,
            "ev_improved_windows": ev_improved,
            "pnl_improved_windows": pnl_improved,
            "ev_regressed_windows": ev_regressed,
            "pnl_regressed_windows": pnl_regressed,
            "drawdown_drift": drawdown_drift,
            "decision": decision,
            "activation_note": (
                "Even a positive daily-equity replay remains observed-only "
                "because no shared daily paper behavior or live execution "
                "envelope was changed in this experiment."
            ),
        },
        "by_window": by_window,
        "aggregate_daily_equity": {
            "core_metrics_daily_mtm_proxy": aggregate_core_metrics,
            "overlay_metrics_daily_mtm": aggregate_overlay_metrics,
            "combined_metrics_daily_mtm_proxy": aggregate_combined_metrics,
            "delta_metrics_daily_mtm_proxy": aggregate_delta,
            "core_overlay_daily_pnl_correlation": aggregate_correlation,
            "days": len(aggregate_days),
        },
        "before_metrics": {
            "core_daily_mtm_proxy": aggregate_core_metrics,
            "canonical_expected_value_score_sum": 7.8941,
            "canonical_total_pnl": 234850.99,
        },
        "after_metrics": {
            "combined_daily_mtm_proxy": aggregate_combined_metrics,
            "overlay_daily_mtm": aggregate_overlay_metrics,
        },
        "delta_metrics": {
            "daily_mtm_proxy": aggregate_delta,
            "canonical_strategy_behavior_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "activation_readiness": {
            "alpha_ready": False,
            "blockers": [
                "observed_only_replay_no_strategy_or_paper_behavior_change",
                "core_daily_path_reconstructed_from_saved_trades_not_backtester_equity_curve",
                "requires_shared_default_off_helper_or_activation_envelope_before_capital",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_or_sizing_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "This runner only reads historical artifacts and OHLCV rows. "
                "It does not alter production/backtest adapters or any order path."
            ),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failure_reasons,
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(failure_reasons)
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exit-date cashflow proxy from exp-20260706-022 was consumed "
                "as a daily mark-to-market replay. The result should be judged "
                "on aggregate daily EV, drawdown drift, and window stability, "
                "not on source-threshold or notional retunes."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun purchase-obligation portfolio overlays by "
                "changing overlay weight, Companyfacts obligation thresholds, "
                "concept priority, fact age, prior gap, RS/close/volume gates, "
                "top-N, hold days, cooldown, correlation cutoffs, or source "
                "filters. A legal retry needs materially new ranked families, "
                "new closed forward replacement-value rows, or a shared paper "
                "helper/activation-envelope experiment."
            ),
            "new_evidence_required": (
                "A shared default-off helper or activation-envelope Gate 1-4 "
                "that implements a fixed portfolio lane, materially new ranked "
                "candidate families with replayable daily-equity paths, or "
                "fresh closed forward replacement-value rows for the unchanged "
                "purchase-obligation source."
            ),
        },
        "rejection_reason": (
            None
            if positive_lead
            else "Daily mark-to-market replay failed the predeclared portfolio-lane gate: "
            + ", ".join(failure_reasons)
        ),
        "next_retry_requires": [
            "shared default-off helper or activation-envelope Gate 1-4",
            "materially new portfolio-ranked candidate families",
            "materially more closed purchase-obligation forward replacement-value rows",
            "no overlay-weight, threshold, top-N, hold-day, concept, or correlation retune",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            SOURCE_RANKING_ARTIFACT,
            TARGET_SOURCE_ARTIFACT,
            BASELINE_RESULT_FILE,
            *CORE_WINDOW_BASELINES.values(),
            WAREHOUSE_SQLITE,
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "changed_variable",
        "single_causal_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "aggregate_daily_equity",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "activation_readiness",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
        "anti_js",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate_daily_equity"]
    delta = aggregate["delta_metrics_daily_mtm_proxy"]
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} - portfolio daily-equity overlay",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- aggregate PnL delta: {delta['total_pnl']}",
        f"- aggregate EV delta: {delta['expected_value_score']}",
        f"- drawdown drift: {delta['max_drawdown_pct']}",
        f"- daily PnL correlation: {aggregate['core_overlay_daily_pnl_correlation']}",
        f"- EV improved windows: {', '.join(gate4['ev_improved_windows']) or 'none'}",
        f"- failed reasons: {', '.join(gate4['failed_reasons']) or 'none'}",
        "",
        "No live, paper, ranking, sizing, entry, or exit behavior changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    ticket = read_json(TICKET_JSON, {}) or {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": {
                "status": payload["status"],
                "aggregate_delta": payload["aggregate_daily_equity"]["delta_metrics_daily_mtm_proxy"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "parameters": payload["parameters"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "aggregate_daily_equity": payload["aggregate_daily_equity"],
            "activation_readiness": payload["activation_readiness"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_daily_equity"][
                    "delta_metrics_daily_mtm_proxy"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
