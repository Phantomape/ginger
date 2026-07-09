"""exp-20260708-027: remaining external trend baseline batch.

Read-only batch diagnostic. After several single external-baseline probes on
July 8, this runner tests the remaining representative OHLCV trend baselines
as one fixed queue decision:

* SPY-residual 12-1 monthly momentum, top 5 positions.
* Absolute time-series momentum, equal-weight all positive 12-1 names.

The output can only be an observed-only lead or a queue-park rejection. It does
not change production strategy, ranking, sizing, orders, paper state, backtester
adapters, or LLM decision boundaries.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-027"
OWNER = "alpha-explore"
SLUG = "external_trend_baseline_batch"
RUNNER = f"quant/experiments/exp_20260708_027_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOW_SOURCES = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
]

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_027_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Batch external-baseline diagnostic: fixed SPY-residual momentum and "
    "absolute time-series momentum representatives should beat the current "
    "trend_long comparator on canonical windows if the external trend baseline "
    "queue contains a deployable entry family rather than more OHLCV relabeling."
)
CHANGE_TYPE = "entry_external_baseline_observed_only_replay"
IMPLEMENTATION_MODE = "read_only_external_baseline_replay"
MECHANISM_FAMILY = "external_trend_baseline_batch"
TRIAL_FAMILY = "remaining_external_trend_baseline_batch"
TRIAL_VARIANT_ID = "residual_and_time_series_momentum_v1"
CHANGED_VARIABLE = "remaining_external_trend_baseline_batch_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_batch_remaining_external_baselines"
NEW_EVIDENCE_AXIS = (
    "Batch remaining representatives from the external baseline queue after "
    "multiple single-lane rejections: SPY-residual momentum and absolute "
    "time-series momentum are different fixed gate shapes from Donchian 55/20, "
    "vanilla 12-1 cross-sectional momentum, chop reversion, or low-vol "
    "admission; no lookback/top-N/threshold retune is allowed."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260708-022",
    "exp-20260708-024",
    "exp-20260708-026",
]
CAUSAL_COMPONENTS = [
    "residual_momentum_representative",
    "time_series_momentum_representative",
    "canonical_window_comparator",
    "read_only_no_strategy_change",
    "queue_park_verdict",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "drawdown_guard_failed",
        "current_trend_long_not_beaten",
        "thin_or_concentrated_representative",
        "no_incremental_external_family",
    ],
    "confidence_reason": (
        "Donchian and vanilla 12-1 momentum already failed; a batch test is "
        "still worth one ID because residualization and absolute time-series "
        "momentum are genuinely different external trend representatives, but "
        "the current trend_long comparator is strong and OHLCV-only relabeling "
        "has high failure risk."
    ),
    "recorded_at": "2026-07-08T19:04:20+00:00",
}

CONFIG = {
    "initial_capital": 100_000.0,
    "lookback_days": 252,
    "skip_recent_days": 21,
    "hold_days": 21,
    "residual_top_n": 5,
    "residual_position_notional": 20_000.0,
    "round_trip_cost_pct": 0.0035,
    "min_price": 5.0,
    "min_avg_dollar_volume_20d": 20_000_000.0,
    "min_regression_observations": 120,
    "annualization_days": 252,
    "max_acceptable_window_drawdown_pct": 0.16,
    "min_trade_count_for_lead": 15,
    "min_win_windows": 2,
    "diagnostic_only": True,
    "acceptance_rule": (
        "Observed-only batch lead only: at least one fixed representative must "
        "beat current trend_long aggregate PnL, win at least two canonical "
        "windows versus trend_long, keep max window drawdown <= 16%, have "
        "trade_count >= 15, and be positive versus cash. A positive result "
        "still requires a shared helper/backtester Gate 1-4 before behavior "
        "changes."
    ),
}

EXCLUDED_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "GLD",
    "IAU",
    "SLV",
    "IEF",
    "TLT",
    "USO",
    "UUP",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}


@dataclass
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    entry_notional: float
    signal_date: str
    planned_exit_date: str
    score: float
    raw_momentum: float
    avg_dollar_volume_20d: float


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def money(value: Any) -> float:
    numeric = as_float(value)
    return 0.0 if numeric is None else numeric


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def valid_bar(row: dict[str, Any]) -> bool:
    return all(money(row.get(field)) > 0.0 for field in ("Open", "High", "Low", "Close"))


def load_snapshot(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    raw = read_json(path, {})
    metadata = raw.get("metadata") or {}
    excluded = set(EXCLUDED_TICKERS)
    excluded.update(str(ticker).upper() for ticker in metadata.get("cross_asset_proxies_added") or [])
    excluded.update(str(ticker).upper() for ticker in metadata.get("added_tickers") or [])

    all_rows: dict[str, list[dict[str, Any]]] = {}
    tradable: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw.get("ohlcv") or {}).items():
        ticker = str(ticker).upper()
        cleaned = [row for row in rows if isinstance(row, dict) and valid_bar(row)]
        cleaned.sort(key=lambda row: str(row.get("Date") or ""))
        if not cleaned:
            continue
        all_rows[ticker] = cleaned
        if ticker not in excluded:
            tradable[ticker] = cleaned
    return all_rows, {
        "metadata": metadata,
        "excluded_tickers": sorted(excluded),
        "eligible_tickers": sorted(tradable),
    }


def avg_dollar_volume(rows: list[dict[str, Any]], end_index: int, lookback: int = 20) -> float | None:
    start = end_index - lookback + 1
    if start < 0:
        return None
    values = [money(row.get("Close")) * money(row.get("Volume")) for row in rows[start : end_index + 1]]
    return statistics.fmean(values) if values else None


def row_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row["Date"]): idx for idx, row in enumerate(rows)}


def rows_by_date(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["Date"]): row for row in rows}


def union_trading_dates(
    ohlcv: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[str]:
    dates = {
        str(row["Date"])
        for rows in ohlcv.values()
        for row in rows
        if start <= str(row.get("Date")) <= end and valid_bar(row)
    }
    return sorted(dates)


def monthly_entry_dates(dates: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for day in dates:
        month = day[:7]
        if month not in seen:
            seen.add(month)
            result.append(day)
    return result


def close_index_for(entry_date: str, rows: list[dict[str, Any]], window_end: str) -> int:
    idx = row_by_date(rows)[entry_date]
    exit_idx = min(idx + CONFIG["hold_days"], len(rows) - 1)
    while exit_idx > idx and str(rows[exit_idx]["Date"]) > window_end:
        exit_idx -= 1
    return exit_idx


def close_position(
    position: Position,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
    variant: str,
) -> dict[str, Any]:
    gross_pnl = (exit_price - position.entry_price) * position.shares
    round_trip_cost = position.entry_notional * CONFIG["round_trip_cost_pct"]
    pnl = gross_pnl - round_trip_cost
    return {
        "ticker": position.ticker,
        "strategy": variant,
        "entry_date": position.entry_date,
        "signal_date": position.signal_date,
        "exit_date": exit_date,
        "exit_reason": exit_reason,
        "entry_price": rounded(position.entry_price, 4),
        "exit_price": rounded(exit_price, 4),
        "shares": position.shares,
        "entry_notional": rounded(position.entry_notional, 2),
        "score": rounded(position.score),
        "raw_momentum": rounded(position.raw_momentum),
        "avg_dollar_volume_20d": rounded(position.avg_dollar_volume_20d, 2),
        "gross_pnl": rounded(gross_pnl, 2),
        "round_trip_cost": rounded(round_trip_cost, 2),
        "pnl": rounded(pnl, 2),
        "pnl_pct_net": rounded(pnl / position.entry_notional if position.entry_notional else 0.0),
    }


def own_momentum_candidate(
    ticker: str,
    rows: list[dict[str, Any]],
    entry_date: str,
) -> tuple[dict[str, Any] | None, str | None]:
    index_by_date = row_by_date(rows)
    entry_idx = index_by_date.get(entry_date)
    if entry_idx is None:
        return None, "missing_entry_bar"
    signal_idx = entry_idx - 1
    score_idx = signal_idx - CONFIG["skip_recent_days"]
    base_idx = signal_idx - CONFIG["lookback_days"]
    if base_idx < 0 or score_idx < 0 or signal_idx < 0:
        return None, "insufficient_history"
    entry_open = money(rows[entry_idx]["Open"])
    signal_close = money(rows[signal_idx]["Close"])
    score_close = money(rows[score_idx]["Close"])
    base_close = money(rows[base_idx]["Close"])
    if min(entry_open, signal_close, score_close, base_close) < CONFIG["min_price"]:
        return None, "price_floor"
    adv20 = avg_dollar_volume(rows, signal_idx)
    if adv20 is None or adv20 < CONFIG["min_avg_dollar_volume_20d"]:
        return None, "liquidity_floor"
    raw_momentum = score_close / base_close - 1.0
    if raw_momentum <= 0.0:
        return None, "nonpositive_time_series_momentum"
    return {
        "ticker": ticker,
        "entry_date": entry_date,
        "signal_date": str(rows[signal_idx]["Date"]),
        "entry_open": entry_open,
        "raw_momentum": raw_momentum,
        "score": raw_momentum,
        "avg_dollar_volume_20d": adv20,
        "base_date": str(rows[base_idx]["Date"]),
        "score_end_date": str(rows[score_idx]["Date"]),
    }, None


def residual_momentum_candidate(
    ticker: str,
    rows: list[dict[str, Any]],
    spy_rows_by_date: dict[str, dict[str, Any]],
    entry_date: str,
) -> tuple[dict[str, Any] | None, str | None]:
    candidate, reason = own_momentum_candidate(ticker, rows, entry_date)
    if candidate is None:
        return None, reason

    index_by_date = row_by_date(rows)
    entry_idx = index_by_date[entry_date]
    signal_idx = entry_idx - 1
    score_idx = signal_idx - CONFIG["skip_recent_days"]
    base_idx = signal_idx - CONFIG["lookback_days"]
    stock_returns: list[float] = []
    spy_returns: list[float] = []
    for idx in range(base_idx + 1, score_idx + 1):
        prev_row = rows[idx - 1]
        cur_row = rows[idx]
        prev_date = str(prev_row["Date"])
        cur_date = str(cur_row["Date"])
        prev_spy = spy_rows_by_date.get(prev_date)
        cur_spy = spy_rows_by_date.get(cur_date)
        if not prev_spy or not cur_spy:
            continue
        prev_stock_close = money(prev_row["Close"])
        cur_stock_close = money(cur_row["Close"])
        prev_spy_close = money(prev_spy["Close"])
        cur_spy_close = money(cur_spy["Close"])
        if min(prev_stock_close, cur_stock_close, prev_spy_close, cur_spy_close) <= 0.0:
            continue
        stock_returns.append(cur_stock_close / prev_stock_close - 1.0)
        spy_returns.append(cur_spy_close / prev_spy_close - 1.0)

    if len(stock_returns) < CONFIG["min_regression_observations"]:
        return None, "insufficient_spy_aligned_returns"
    spy_mean = statistics.fmean(spy_returns)
    stock_mean = statistics.fmean(stock_returns)
    variance = sum((value - spy_mean) ** 2 for value in spy_returns)
    if variance <= 0.0:
        return None, "zero_spy_variance"
    covariance = sum(
        (stock - stock_mean) * (spy - spy_mean)
        for stock, spy in zip(stock_returns, spy_returns)
    )
    beta = covariance / variance
    residuals = [stock - beta * spy for stock, spy in zip(stock_returns, spy_returns)]
    residual_score = sum(residuals)
    if residual_score <= 0.0:
        return None, "nonpositive_residual_momentum"
    candidate = dict(candidate)
    candidate.update(
        {
            "score": residual_score,
            "spy_beta": beta,
            "regression_observations": len(stock_returns),
        }
    )
    return candidate, None


def rank_residual_candidates(
    tradable: dict[str, list[dict[str, Any]]],
    spy_rows_by_date: dict[str, dict[str, Any]],
    entry_date: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rejected: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    for ticker, rows in tradable.items():
        candidate, reason = residual_momentum_candidate(ticker, rows, spy_rows_by_date, entry_date)
        if candidate is None:
            rejected[str(reason)] = rejected.get(str(reason), 0) + 1
            continue
        candidates.append(candidate)
    candidates.sort(
        key=lambda row: (
            money(row["score"]),
            money(row["raw_momentum"]),
            money(row["avg_dollar_volume_20d"]),
            str(row["ticker"]),
        ),
        reverse=True,
    )
    return candidates, rejected


def rank_time_series_candidates(
    tradable: dict[str, list[dict[str, Any]]],
    entry_date: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rejected: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    for ticker, rows in tradable.items():
        candidate, reason = own_momentum_candidate(ticker, rows, entry_date)
        if candidate is None:
            rejected[str(reason)] = rejected.get(str(reason), 0) + 1
            continue
        candidates.append(candidate)
    candidates.sort(
        key=lambda row: (
            str(row["ticker"]),
        )
    )
    return candidates, rejected


def summarize_returns(label: str, equity_curve: list[dict[str, Any]]) -> dict[str, Any]:
    if not equity_curve:
        return {
            "label": label,
            "trading_days": 0,
            "total_return_pct": 0.0,
            "expected_value_score": 0.0,
            "sharpe_daily": 0.0,
            "max_drawdown_pct": 0.0,
            "ending_equity": CONFIG["initial_capital"],
        }
    equities = [money(row["equity"]) for row in equity_curve]
    total_return = equities[-1] / CONFIG["initial_capital"] - 1.0
    returns: list[float] = []
    for prev, cur in zip(equities, equities[1:]):
        if prev > 0:
            returns.append(cur / prev - 1.0)
    if len(returns) > 1:
        stdev = statistics.stdev(returns)
        mean_ret = statistics.fmean(returns)
        sharpe = mean_ret / stdev * math.sqrt(CONFIG["annualization_days"]) if stdev else 0.0
    else:
        sharpe = 0.0
    peak = equities[0]
    max_dd = 0.0
    for value in equities:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return {
        "label": label,
        "trading_days": len(equity_curve),
        "total_return_pct": rounded(total_return),
        "expected_value_score": rounded(total_return * sharpe),
        "sharpe_daily": rounded(sharpe),
        "max_drawdown_pct": rounded(abs(max_dd)),
        "ending_equity": rounded(equities[-1], 2),
    }


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [money(trade.get("pnl")) for trade in trades]
    wins = sum(1 for value in pnls if value > 0)
    losses = sum(1 for value in pnls if value < 0)
    ticker_counts: dict[str, int] = {}
    for trade in trades:
        ticker = str(trade.get("ticker"))
        ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
    max_ticker_share = max(ticker_counts.values(), default=0) / len(trades) if trades else 0.0
    return {
        "trade_count": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": rounded(wins / len(trades), 4) if trades else None,
        "total_pnl": rounded(sum(pnls), 2),
        "avg_pnl": rounded(statistics.fmean(pnls), 2) if pnls else None,
        "largest_winner": rounded(max(pnls), 2) if pnls else None,
        "largest_loser": rounded(min(pnls), 2) if pnls else None,
        "ticker_count": len(ticker_counts),
        "max_ticker_share": rounded(max_ticker_share, 4),
        "top_tickers": sorted(
            [{"ticker": ticker, "trades": count} for ticker, count in ticker_counts.items()],
            key=lambda row: (-row["trades"], row["ticker"]),
        )[:8],
    }


def trade_samples(trades: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    sorted_trades = sorted(trades, key=lambda row: money(row.get("pnl")))
    return {
        "worst": sorted_trades[:5],
        "best": list(reversed(sorted_trades[-5:])),
    }


def current_trend_long_summary(core_result_path: Path) -> dict[str, Any]:
    result = read_json(core_result_path, {})
    by_strategy = result.get("by_strategy") or {}
    trend = dict(by_strategy.get("trend_long") or {})
    return {
        "trade_count": int(trend.get("trade_count") or 0),
        "total_pnl_usd": rounded(money(trend.get("total_pnl_usd")), 2),
        "win_rate": trend.get("win_rate"),
        "source": repo_rel(core_result_path),
    }


def simulate_variant(
    source: dict[str, Any],
    variant: str,
    all_rows: dict[str, list[dict[str, Any]]],
    universe: dict[str, Any],
) -> dict[str, Any]:
    tradable = {ticker: all_rows[ticker] for ticker in universe["eligible_tickers"] if ticker in all_rows}
    dates = union_trading_dates(tradable, source["start"], source["end"])
    rebalance_dates = set(monthly_entry_dates(dates))
    bars_by_ticker = {ticker: rows_by_date(rows) for ticker, rows in tradable.items()}
    positions: dict[str, Position] = {}
    closed_trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    realized_pnl = 0.0
    reject_counts: dict[str, int] = {}
    rebalance_summaries: list[dict[str, Any]] = []
    spy_rows_by_date = rows_by_date(all_rows.get("SPY", []))

    for current_date in dates:
        for ticker in list(positions):
            position = positions[ticker]
            if current_date < position.planned_exit_date:
                continue
            bar = bars_by_ticker.get(ticker, {}).get(current_date)
            if not bar:
                continue
            trade = close_position(
                position,
                current_date,
                money(bar["Close"]),
                "fixed_21_session_close",
                variant,
            )
            realized_pnl += money(trade["pnl"])
            closed_trades.append(trade)
            del positions[ticker]

        if current_date in rebalance_dates and not positions:
            if variant == "spy_residual_momentum_top5":
                ranked, rejected = rank_residual_candidates(tradable, spy_rows_by_date, current_date)
                selected = ranked[: CONFIG["residual_top_n"]]
                notional_for = lambda _count: CONFIG["residual_position_notional"]
            elif variant == "absolute_time_series_momentum_equal_weight":
                ranked, rejected = rank_time_series_candidates(tradable, current_date)
                selected = ranked
                notional_for = lambda count: CONFIG["initial_capital"] / count if count else 0.0
            else:
                raise ValueError(f"unknown variant: {variant}")

            for reason, count in rejected.items():
                reject_counts[reason] = reject_counts.get(reason, 0) + count

            opened: list[str] = []
            per_position_notional = notional_for(len(selected))
            for candidate in selected:
                ticker = str(candidate["ticker"])
                entry_price = money(candidate["entry_open"])
                shares = int(per_position_notional / entry_price)
                if shares <= 0:
                    reject_counts["zero_shares"] = reject_counts.get("zero_shares", 0) + 1
                    continue
                exit_idx = close_index_for(current_date, tradable[ticker], source["end"])
                planned_exit = str(tradable[ticker][exit_idx]["Date"])
                positions[ticker] = Position(
                    ticker=ticker,
                    entry_date=current_date,
                    entry_price=entry_price,
                    shares=shares,
                    entry_notional=shares * entry_price,
                    signal_date=str(candidate["signal_date"]),
                    planned_exit_date=planned_exit,
                    score=money(candidate["score"]),
                    raw_momentum=money(candidate["raw_momentum"]),
                    avg_dollar_volume_20d=money(candidate["avg_dollar_volume_20d"]),
                )
                opened.append(ticker)

            rebalance_summaries.append(
                {
                    "entry_date": current_date,
                    "eligible_candidate_count": len(ranked),
                    "opened_count": len(opened),
                    "opened": opened[:12],
                    "top_candidates": [
                        {
                            "ticker": row["ticker"],
                            "score": rounded(money(row["score"])),
                            "raw_momentum": rounded(money(row["raw_momentum"])),
                        }
                        for row in ranked[:5]
                    ],
                }
            )

        unrealized = 0.0
        gross_notional = 0.0
        for ticker, position in positions.items():
            bar = bars_by_ticker.get(ticker, {}).get(current_date)
            if not bar:
                continue
            close_price = money(bar["Close"])
            unrealized += (close_price - position.entry_price) * position.shares
            gross_notional += position.entry_notional
        equity_curve.append(
            {
                "date": current_date,
                "equity": rounded(CONFIG["initial_capital"] + realized_pnl + unrealized, 2),
                "open_positions": len(positions),
                "gross_notional": rounded(gross_notional, 2),
            }
        )

    last_date = dates[-1] if dates else source["end"]
    for ticker in list(positions):
        position = positions[ticker]
        bar = bars_by_ticker.get(ticker, {}).get(last_date)
        if not bar:
            continue
        trade = close_position(
            position,
            last_date,
            money(bar["Close"]),
            "forced_window_end_close",
            variant,
        )
        realized_pnl += money(trade["pnl"])
        closed_trades.append(trade)
        del positions[ticker]
    if equity_curve:
        equity_curve[-1]["equity"] = rounded(CONFIG["initial_capital"] + realized_pnl, 2)
        equity_curve[-1]["open_positions"] = 0
        equity_curve[-1]["gross_notional"] = 0.0

    return {
        "variant": variant,
        "metrics": summarize_returns(variant, equity_curve),
        "trade_summary": summarize_trades(closed_trades),
        "sample_trades": trade_samples(closed_trades),
        "signal_diagnostics": {
            "rebalance_count": len(rebalance_summaries),
            "candidate_open_count": sum(len(row["opened"]) for row in rebalance_summaries),
            "eligible_candidate_count_sum": sum(row["eligible_candidate_count"] for row in rebalance_summaries),
            "reject_counts": reject_counts,
            "rebalance_summaries_sample": rebalance_summaries[:8],
        },
    }


def simulate_window(source: dict[str, Any]) -> dict[str, Any]:
    all_rows, universe = load_snapshot(source["snapshot"])
    variants = {
        "spy_residual_momentum_top5": simulate_variant(
            source, "spy_residual_momentum_top5", all_rows, universe
        ),
        "absolute_time_series_momentum_equal_weight": simulate_variant(
            source, "absolute_time_series_momentum_equal_weight", all_rows, universe
        ),
    }
    trend = current_trend_long_summary(source["core_result"])
    comparisons: dict[str, dict[str, Any]] = {}
    for name, result in variants.items():
        pnl = money(result["trade_summary"]["total_pnl"])
        comparisons[name] = {
            "pnl_delta_vs_trend_long": rounded(pnl - money(trend["total_pnl_usd"]), 2),
            "beats_trend_long_pnl": pnl > money(trend["total_pnl_usd"]),
        }
    return {
        "label": source["label"],
        "start": source["start"],
        "end": source["end"],
        "snapshot": repo_rel(source["snapshot"]),
        "universe": universe,
        "current_trend_long": trend,
        "variants": variants,
        "comparisons_vs_trend_long": comparisons,
    }


def aggregate_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    trend_total = sum(money(row["current_trend_long"]["total_pnl_usd"]) for row in windows)
    trend_trades = sum(int(row["current_trend_long"]["trade_count"]) for row in windows)
    variants: dict[str, dict[str, Any]] = {}
    for variant in (
        "spy_residual_momentum_top5",
        "absolute_time_series_momentum_equal_weight",
    ):
        total_pnl = sum(money(row["variants"][variant]["trade_summary"]["total_pnl"]) for row in windows)
        trade_count = sum(int(row["variants"][variant]["trade_summary"]["trade_count"]) for row in windows)
        win_windows = [
            row["label"]
            for row in windows
            if row["comparisons_vs_trend_long"][variant]["beats_trend_long_pnl"]
        ]
        max_dd = max(money(row["variants"][variant]["metrics"]["max_drawdown_pct"]) for row in windows)
        total_return = total_pnl / CONFIG["initial_capital"]
        mean_sharpe = statistics.fmean(
            [money(row["variants"][variant]["metrics"]["sharpe_daily"]) for row in windows]
        )
        variants[variant] = {
            "total_pnl": rounded(total_pnl, 2),
            "trade_count": trade_count,
            "current_trend_long_total_pnl": rounded(trend_total, 2),
            "current_trend_long_trade_count": trend_trades,
            "pnl_delta_vs_trend_long": rounded(total_pnl - trend_total, 2),
            "win_window_count_vs_trend_long": len(win_windows),
            "win_windows_vs_trend_long": win_windows,
            "max_window_drawdown_pct": rounded(max_dd),
            "diagnostic_total_return_pct": rounded(total_return),
            "mean_window_sharpe_daily": rounded(mean_sharpe),
            "diagnostic_expected_value_score": rounded(total_return * mean_sharpe),
        }
    return {
        "current_trend_long_total_pnl": rounded(trend_total, 2),
        "current_trend_long_trade_count": trend_trades,
        "variants": variants,
    }


def representative_failures(summary: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if money(summary["total_pnl"]) <= money(summary["current_trend_long_total_pnl"]):
        failed.append("aggregate_pnl_not_above_current_trend_long")
    if int(summary["win_window_count_vs_trend_long"]) < CONFIG["min_win_windows"]:
        failed.append("fewer_than_two_windows_beat_trend_long")
    if int(summary["trade_count"]) < CONFIG["min_trade_count_for_lead"]:
        failed.append("trade_count_below_floor")
    if money(summary["max_window_drawdown_pct"]) > CONFIG["max_acceptable_window_drawdown_pct"]:
        failed.append("drawdown_above_guard")
    if money(summary["total_pnl"]) <= 0:
        failed.append("not_positive_vs_cash")
    return failed


def evaluate_batch(aggregate: dict[str, Any]) -> tuple[bool, dict[str, list[str]]]:
    failed_by_variant = {
        variant: representative_failures(summary)
        for variant, summary in aggregate["variants"].items()
    }
    observed_only_lead = any(not failures for failures in failed_by_variant.values())
    return observed_only_lead, failed_by_variant


def compact_gate4(gate4: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_only": gate4["diagnostic_only"],
        "observed_only_lead": gate4["observed_only_lead"],
        "full_gate4_passed": gate4["full_gate4_passed"],
        "failed_reasons_by_variant": gate4["failed_reasons_by_variant"],
        "aggregate": gate4["aggregate"],
        "windows": [
            {
                "label": row["label"],
                "trend_long_total_pnl": row["current_trend_long"]["total_pnl_usd"],
                "variants": {
                    name: {
                        "total_pnl": variant["trade_summary"]["total_pnl"],
                        "trade_count": variant["trade_summary"]["trade_count"],
                        "ev": variant["metrics"]["expected_value_score"],
                        "max_drawdown_pct": variant["metrics"]["max_drawdown_pct"],
                        "pnl_delta_vs_trend_long": row["comparisons_vs_trend_long"][name][
                            "pnl_delta_vs_trend_long"
                        ],
                        "beats_trend_long_pnl": row["comparisons_vs_trend_long"][name][
                            "beats_trend_long_pnl"
                        ],
                    }
                    for name, variant in row["variants"].items()
                },
            }
            for row in gate4["windows"]
        ],
        "acceptance_rule": gate4["acceptance_rule"],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    windows = [simulate_window(source) for source in WINDOW_SOURCES]
    aggregate = aggregate_windows(windows)
    observed_only_lead, failed_by_variant = evaluate_batch(aggregate)
    full_gate4_passed = False
    decision = (
        "observed_only_lead_external_trend_baseline_batch_requires_shared_gate_1_4"
        if observed_only_lead
        else "observed_only_rejected_external_trend_baseline_batch_queue_parked"
    )
    if observed_only_lead:
        why = (
            "At least one fixed remaining external trend representative cleared "
            "the private replay lead bar. This is still not accepted behavior "
            "because production candidate generation, slot displacement, daily "
            "paper state, and live order semantics were not replayed through a "
            "shared helper."
        )
        next_retry = [
            "shared_helper_gate_1_4_before_any_behavior_change",
            "no_residual_or_time_series_lookback_topn_threshold_cost_universe_notional_retune_on_same_windows",
        ]
    else:
        why = (
            "Neither fixed remaining external trend representative cleared the "
            "predeclared private replay bar versus current trend_long. This "
            "finishes the July 8 external OHLCV trend baseline queue without a "
            "deployable lead."
        )
        next_retry = [
            "park_external_ohlcv_trend_baseline_queue",
            "reopen_only_with_new_data_source_material_forward_rows_or_shared_helper_required_by_positive_lead",
            "no_more_single_external_ohlcv_momentum_baseline_ids_from_this_queue",
        ]
    production_impact = {
        "strategy_code_changed": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "paper_state_changed": False,
        "llm_decision_boundary_changed": False,
        "trade_enabled": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_external_trend_baseline_batch_replay",
    }
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    completed_at = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": int(bool(observed_only_lead)),
            "brier_score": rounded((PREDICTION["success_probability"] - int(bool(observed_only_lead))) ** 2, 4),
            "realized_failure_modes": failed_by_variant,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "predicted_failure_mode_hit": not observed_only_lead,
            "surprise_note": (
                "Low surprise: prior Donchian and 12-1 results made another "
                "OHLCV-only external trend lead unlikely."
            ),
        },
        "config": CONFIG,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "gate1": {
            "baseline_available": BASELINE_RESULT.exists(),
            "canonical_snapshots": [repo_rel(row["snapshot"]) for row in WINDOW_SOURCES],
            "canonical_core_results": [repo_rel(row["core_result"]) for row in WINDOW_SOURCES],
            "baseline_protocol": (
                "private external residual/time-series momentum batch replay "
                "compared to accepted current trend_long by_strategy rows"
            ),
            "passed": BASELINE_RESULT.exists()
            and all(Path(row["snapshot"]).exists() for row in WINDOW_SOURCES)
            and all(Path(row["core_result"]).exists() for row in WINDOW_SOURCES),
        },
        "gate2": {
            "required_fields": ["Date", "Open", "High", "Low", "Close", "Volume"],
            "entry_date_contract": "entry fills use monthly rebalance Open after signal-date close",
            "target_price_required_for_signal_generation": False,
            "uses_runtime_production_visible_fields": True,
            "passed": True,
        },
        "gate3": {
            "no_filter_added_to_strategy": True,
            "private_replay_trade_counts": {
                variant: summary["trade_count"] for variant, summary in aggregate["variants"].items()
            },
            "survival_rate": 1.0,
            "passed": all(
                summary["trade_count"] >= CONFIG["min_trade_count_for_lead"]
                for summary in aggregate["variants"].values()
            ),
        },
        "gate4": {
            "diagnostic_only": True,
            "full_gate4_passed": full_gate4_passed,
            "observed_only_lead": observed_only_lead,
            "failed_reasons_by_variant": {
                key: value + ["not_full_gate4_private_external_replay"]
                for key, value in failed_by_variant.items()
            },
            "aggregate": aggregate,
            "windows": windows,
            "acceptance_rule": CONFIG["acceptance_rule"],
            "not_recomputed_in_shared_backtester": [
                "production candidate generation",
                "slot displacement against core positions",
                "daily paper state",
                "live order semantics",
            ],
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not consume more single OHLCV external trend baselines from "
                "the July 8 plan by changing residual lookback, beta benchmark, "
                "time-series positive threshold, top-N, hold days, liquidity "
                "floors, universe exclusions, costs, notional, or tie-breaks on "
                "the same frozen windows."
            ),
            "new_evidence_required": (
                "A legal retry needs a genuinely new data source, materially "
                "more settled forward replacement-value rows from a fixed "
                "shared logger, or a positive batch representative promoted "
                "through shared production/backtest Gate 1-4."
            ),
        },
        "rejection_reason": None if observed_only_lead else json.dumps(failed_by_variant, sort_keys=True),
        "next_retry_requires": next_retry,
        "changed_files": changed_files,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            *[repo_rel(row["snapshot"]) for row in WINDOW_SOURCES],
            *[repo_rel(row["core_result"]) for row in WINDOW_SOURCES],
            repo_rel(TICKET_JSON),
        ],
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "ticket_before": ticket,
        "completed_at": completed_at,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": compact_gate4(payload["gate4"]),
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "completed_at": payload["completed_at"],
    }


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: External Trend Baseline Batch",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Observed-only lead: `{payload['observed_only_lead']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Aggregate",
        "",
        f"- Current `trend_long` PnL: `${aggregate['current_trend_long_total_pnl']}`",
        f"- Current `trend_long` trades: `{aggregate['current_trend_long_trade_count']}`",
        "",
        "| Variant | PnL | Trades | Delta vs trend_long | Windows won | Max DD | EV | Failed reasons |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for variant, summary in aggregate["variants"].items():
        failures = gate4["failed_reasons_by_variant"][variant]
        lines.append(
            f"| {variant} | {summary['total_pnl']} | {summary['trade_count']} | "
            f"{summary['pnl_delta_vs_trend_long']} | "
            f"{summary['win_window_count_vs_trend_long']} | "
            f"{summary['max_window_drawdown_pct']} | "
            f"{summary['diagnostic_expected_value_score']} | "
            f"{', '.join(failures) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Windows",
            "",
            "| Window | trend_long PnL | residual PnL | residual delta | tsmom PnL | tsmom delta |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in gate4["windows"]:
        residual = row["variants"]["spy_residual_momentum_top5"]
        tsmom = row["variants"]["absolute_time_series_momentum_equal_weight"]
        lines.append(
            f"| {row['label']} | {row['current_trend_long']['total_pnl_usd']} | "
            f"{residual['trade_summary']['total_pnl']} | "
            f"{row['comparisons_vs_trend_long']['spy_residual_momentum_top5']['pnl_delta_vs_trend_long']} | "
            f"{tsmom['trade_summary']['total_pnl']} | "
            f"{row['comparisons_vs_trend_long']['absolute_time_series_momentum_equal_weight']['pnl_delta_vs_trend_long']} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_record = compact_log_record(payload)
    ticket = dict(payload["ticket_before"] or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["completed_at"],
            "result": {
                "decision": payload["decision"],
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "observed_only_lead": payload["observed_only_lead"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "gate4": log_record["gate4"],
            },
        }
    )

    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, ticket)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "runner": RUNNER,
            "gate4": log_record["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": log_record["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "gate4": compact_gate4(payload["gate4"]),
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
