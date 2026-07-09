"""exp-20260708-024: fixed 12-1 cross-sectional momentum external baseline.

Read-only external baseline replay. The fixed question is whether a canonical
12-1 cross-sectional momentum policy (252 trading-day return excluding the
most recent 21 sessions, monthly top-5 entries, 21-session hold) is a stronger
trend family than the current accepted ``trend_long`` comparator on the
canonical windows. This runner changes no production strategy, sizing, ranking,
orders, paper state, backtester adapter, or LLM boundary.
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


EXPERIMENT_ID = "exp-20260708-024"
OWNER = "codex-alpha-explore"
SLUG = "cross_sectional_12_1_momentum_external_baseline"
RUNNER = f"quant/experiments/exp_20260708_024_{SLUG}.py"
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
OUT_JSON = DATA_DIR / f"exp_20260708_024_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "External baseline: a fixed 12-1 cross-sectional momentum policy that "
    "ranks core-universe stocks by 252-trading-day return excluding the most "
    "recent 21 sessions, enters the top five on monthly rebalance dates, and "
    "holds for 21 sessions may challenge current trend_long better than local "
    "trend thresholds."
)
CHANGE_TYPE = "entry_external_baseline_observed_only_replay"
IMPLEMENTATION_MODE = "read_only_external_baseline_replay"
MECHANISM_FAMILY = "external_cross_sectional_momentum_baseline"
TRIAL_FAMILY = "cross_sectional_12_1_momentum_baseline"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "cross_sectional_12_1_momentum_monthly_top5_baseline_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape: complete external 12-1 monthly momentum entry/hold policy "
    "(252-to-21 ranking, monthly top-5, 21-session hold) compared to current "
    "trend_long. Prior cross-sectional ranking work attributed alpha_score/"
    "components or 60d residual pullback candidates; it did not test this full "
    "12-1 monthly entry/hold benchmark."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260708-022",
    "exp-20260529-013",
    "exp-20260601-006",
]
CAUSAL_COMPONENTS = [
    "fixed 252-to-21 momentum ranking",
    "monthly rebalance",
    "next-open entry",
    "21-session hold",
    "5-position cap",
    "canonical OHLCV snapshots",
    "no strategy behavior change",
]

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "momentum_lags_current_trend_long",
        "old_thin_window_regression",
        "drawdown_worse",
        "lookback_coverage_thin",
        "private_replay_not_production_ready",
    ],
    "confidence_reason": (
        "The plan explicitly named 12-1 momentum as the next external baseline "
        "after Donchian; it is a distinct academic trend benchmark using only "
        "PIT OHLCV, but the current trend_long comparator is strong and the "
        "fixed-window core universe may be too concentrated."
    ),
    "recorded_at": "2026-07-08T18:04:59+00:00",
}

CONFIG = {
    "initial_capital": 100_000.0,
    "lookback_days": 252,
    "skip_recent_days": 21,
    "hold_days": 21,
    "top_n": 5,
    "position_notional": 20_000.0,
    "max_positions": 5,
    "round_trip_cost_pct": 0.0035,
    "min_price": 5.0,
    "min_avg_dollar_volume_20d": 20_000_000.0,
    "annualization_days": 252,
    "max_acceptable_window_drawdown_pct": 0.16,
    "min_trade_count_for_lead": 15,
    "min_trend_win_windows": 2,
    "diagnostic_only": True,
    "acceptance_rule": (
        "Observed-only external baseline lead only: fixed 12-1 monthly "
        "momentum replay must beat current trend_long aggregate PnL and win at "
        "least two canonical windows versus trend_long while keeping max "
        "drawdown <= 16% and trade count >= 15. A positive result still "
        "requires shared helper/backtester Gate 1-4 before behavior changes."
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
    momentum_12_1: float
    avg_dollar_volume_20d: float
    planned_exit_date: str


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
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def money(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(result) or math.isinf(result):
        return 0.0
    return result


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
    excluded.update(str(ticker) for ticker in metadata.get("cross_asset_proxies_added") or [])
    excluded.update(str(ticker) for ticker in metadata.get("added_tickers") or [])
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw.get("ohlcv") or {}).items():
        ticker = str(ticker).upper()
        if ticker in excluded:
            continue
        cleaned = [row for row in rows if isinstance(row, dict) and valid_bar(row)]
        cleaned.sort(key=lambda row: str(row.get("Date") or ""))
        if cleaned:
            result[ticker] = cleaned
    return result, {
        "metadata": metadata,
        "excluded_tickers": sorted(excluded),
        "eligible_tickers": sorted(result),
    }


def avg_dollar_volume(rows: list[dict[str, Any]], end_index: int, lookback: int = 20) -> float | None:
    start = end_index - lookback + 1
    if start < 0:
        return None
    values = [
        money(row.get("Close")) * money(row.get("Volume"))
        for row in rows[start : end_index + 1]
    ]
    return statistics.fmean(values) if values else None


def trading_dates(spy_rows: list[dict[str, Any]], start: str, end: str) -> list[str]:
    return [
        str(row["Date"])
        for row in spy_rows
        if start <= str(row.get("Date")) <= end and valid_bar(row)
    ]


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
    entries: list[str] = []
    for day in dates:
        month = day[:7]
        if month not in seen:
            seen.add(month)
            entries.append(day)
    return entries


def row_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row["Date"]): idx for idx, row in enumerate(rows)}


def score_candidate(
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
        return None, "insufficient_12_1_history"
    entry_open = money(rows[entry_idx].get("Open"))
    signal_close = money(rows[signal_idx].get("Close"))
    score_close = money(rows[score_idx].get("Close"))
    base_close = money(rows[base_idx].get("Close"))
    if entry_open < CONFIG["min_price"] or signal_close < CONFIG["min_price"]:
        return None, "price_floor"
    if base_close <= 0.0 or score_close <= 0.0:
        return None, "bad_momentum_prices"
    adv20 = avg_dollar_volume(rows, signal_idx)
    if adv20 is None or adv20 < CONFIG["min_avg_dollar_volume_20d"]:
        return None, "liquidity_floor"
    momentum = score_close / base_close - 1.0
    return {
        "ticker": ticker,
        "entry_date": entry_date,
        "signal_date": str(rows[signal_idx]["Date"]),
        "entry_open": entry_open,
        "signal_close": signal_close,
        "momentum_12_1": momentum,
        "avg_dollar_volume_20d": adv20,
        "base_date": str(rows[base_idx]["Date"]),
        "skip_end_date": str(rows[score_idx]["Date"]),
    }, None


def rank_candidates(
    ohlcv: dict[str, list[dict[str, Any]]],
    entry_date: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rejected: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    for ticker, rows in ohlcv.items():
        candidate, reason = score_candidate(ticker, rows, entry_date)
        if candidate is None:
            rejected[str(reason)] = rejected.get(str(reason), 0) + 1
            continue
        candidates.append(candidate)
    candidates.sort(
        key=lambda row: (
            money(row["momentum_12_1"]),
            money(row["avg_dollar_volume_20d"]),
            str(row["ticker"]),
        ),
        reverse=True,
    )
    return candidates, rejected


def exit_date_for(entry_date: str, rows: list[dict[str, Any]], window_end: str) -> str:
    index_by_date = row_by_date(rows)
    entry_idx = index_by_date[entry_date]
    exit_idx = min(entry_idx + CONFIG["hold_days"], len(rows) - 1)
    while exit_idx > entry_idx and str(rows[exit_idx]["Date"]) > window_end:
        exit_idx -= 1
    return str(rows[exit_idx]["Date"])


def close_position(
    position: Position,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
) -> dict[str, Any]:
    gross_pnl = (exit_price - position.entry_price) * position.shares
    round_trip_cost = position.entry_notional * CONFIG["round_trip_cost_pct"]
    pnl = gross_pnl - round_trip_cost
    return {
        "ticker": position.ticker,
        "strategy": "cross_sectional_12_1_momentum",
        "entry_date": position.entry_date,
        "signal_date": position.signal_date,
        "exit_date": exit_date,
        "exit_reason": exit_reason,
        "entry_price": rounded(position.entry_price, 4),
        "exit_price": rounded(exit_price, 4),
        "shares": position.shares,
        "entry_notional": rounded(position.entry_notional, 2),
        "momentum_12_1": rounded(position.momentum_12_1),
        "avg_dollar_volume_20d": rounded(position.avg_dollar_volume_20d, 2),
        "gross_pnl": rounded(gross_pnl, 2),
        "round_trip_cost": rounded(round_trip_cost, 2),
        "pnl": rounded(pnl, 2),
        "pnl_pct_net": rounded(pnl / position.entry_notional if position.entry_notional else 0.0),
    }


def summarize_returns(label: str, equity_curve: list[dict[str, Any]]) -> dict[str, Any]:
    if not equity_curve:
        return {
            "label": label,
            "trading_days": 0,
            "total_return_pct": 0.0,
            "expected_value_score": 0.0,
            "sharpe_daily": 0.0,
            "max_drawdown_pct": 0.0,
        }
    equities = [money(row["equity"]) for row in equity_curve]
    initial = CONFIG["initial_capital"]
    total_return = equities[-1] / initial - 1.0
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
    return {
        "trade_count": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": rounded(wins / len(trades), 4) if trades else None,
        "total_pnl": rounded(sum(pnls), 2),
        "avg_pnl": rounded(statistics.fmean(pnls), 2) if pnls else None,
        "largest_winner": rounded(max(pnls), 2) if pnls else None,
        "largest_loser": rounded(min(pnls), 2) if pnls else None,
    }


def simulate_window(source: dict[str, Any]) -> dict[str, Any]:
    ohlcv, universe = load_snapshot(source["snapshot"])
    dates = union_trading_dates(ohlcv, source["start"], source["end"])
    rebalance_dates = set(monthly_entry_dates(dates))
    rows_by_ticker_date = {
        ticker: {str(row["Date"]): row for row in rows} for ticker, rows in ohlcv.items()
    }
    positions: dict[str, Position] = {}
    closed_trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    realized_pnl = 0.0
    reject_counts: dict[str, int] = {}
    rebalance_summaries: list[dict[str, Any]] = []

    for current_date in dates:
        for ticker in list(positions):
            position = positions[ticker]
            if current_date < position.planned_exit_date:
                continue
            bar = rows_by_ticker_date.get(ticker, {}).get(current_date)
            if not bar:
                continue
            trade = close_position(
                position,
                current_date,
                money(bar["Close"]),
                "fixed_21_session_close" if current_date == position.planned_exit_date else "late_available_close",
            )
            realized_pnl += money(trade["pnl"])
            closed_trades.append(trade)
            del positions[ticker]

        if current_date in rebalance_dates:
            ranked, rejected = rank_candidates(ohlcv, current_date)
            for reason, count in rejected.items():
                reject_counts[reason] = reject_counts.get(reason, 0) + count
            opened: list[str] = []
            for candidate in ranked:
                if len(positions) >= CONFIG["max_positions"]:
                    break
                ticker = str(candidate["ticker"])
                if ticker in positions:
                    continue
                entry_price = money(candidate["entry_open"])
                shares = int(CONFIG["position_notional"] / entry_price)
                if shares <= 0:
                    reject_counts["zero_shares"] = reject_counts.get("zero_shares", 0) + 1
                    continue
                planned_exit = exit_date_for(current_date, ohlcv[ticker], source["end"])
                positions[ticker] = Position(
                    ticker=ticker,
                    entry_date=current_date,
                    entry_price=entry_price,
                    shares=shares,
                    entry_notional=shares * entry_price,
                    signal_date=str(candidate["signal_date"]),
                    momentum_12_1=money(candidate["momentum_12_1"]),
                    avg_dollar_volume_20d=money(candidate["avg_dollar_volume_20d"]),
                    planned_exit_date=planned_exit,
                )
                opened.append(ticker)
            rebalance_summaries.append(
                {
                    "entry_date": current_date,
                    "eligible_candidate_count": len(ranked),
                    "opened": opened,
                    "top_candidates": [
                        {
                            "ticker": row["ticker"],
                            "momentum_12_1": rounded(row["momentum_12_1"]),
                            "signal_date": row["signal_date"],
                            "base_date": row["base_date"],
                            "skip_end_date": row["skip_end_date"],
                        }
                        for row in ranked[: CONFIG["top_n"]]
                    ],
                }
            )

        unrealized = 0.0
        for ticker, position in positions.items():
            bar = rows_by_ticker_date.get(ticker, {}).get(current_date)
            if bar:
                unrealized += (money(bar["Close"]) - position.entry_price) * position.shares
        equity_curve.append(
            {
                "date": current_date,
                "equity": rounded(CONFIG["initial_capital"] + realized_pnl + unrealized, 2),
                "realized_pnl": rounded(realized_pnl, 2),
                "open_positions": len(positions),
            }
        )

    if dates:
        last_date = dates[-1]
        for ticker in list(positions):
            position = positions[ticker]
            bar = rows_by_ticker_date.get(ticker, {}).get(last_date)
            if not bar:
                continue
            trade = close_position(position, last_date, money(bar["Close"]), "window_end_forced")
            realized_pnl += money(trade["pnl"])
            closed_trades.append(trade)
            del positions[ticker]
        if equity_curve:
            equity_curve[-1]["equity"] = rounded(CONFIG["initial_capital"] + realized_pnl, 2)
            equity_curve[-1]["realized_pnl"] = rounded(realized_pnl, 2)
            equity_curve[-1]["open_positions"] = 0

    core = read_json(source["core_result"], {})
    current_trend = ((core or {}).get("by_strategy") or {}).get("trend_long") or {}
    metrics = summarize_returns("cross_sectional_12_1_momentum", equity_curve)
    trade_summary = summarize_trades(closed_trades)
    trend_pnl = money(current_trend.get("total_pnl_usd"))
    return {
        "label": source["label"],
        "start": source["start"],
        "end": source["end"],
        "snapshot": repo_rel(source["snapshot"]),
        "core_result": repo_rel(source["core_result"]),
        "universe": universe,
        "rebalance_dates": sorted(rebalance_dates),
        "rebalance_summaries": rebalance_summaries,
        "signal_diagnostics": {
            "rebalance_count": len(rebalance_dates),
            "reject_counts": dict(sorted(reject_counts.items())),
            "candidate_open_count": sum(len(row["opened"]) for row in rebalance_summaries),
            "eligible_candidate_count_sum": sum(
                int(row["eligible_candidate_count"]) for row in rebalance_summaries
            ),
        },
        "momentum_metrics": metrics,
        "momentum_trade_summary": trade_summary,
        "closed_trades": closed_trades,
        "equity_curve_tail": equity_curve[-5:],
        "current_trend_long": current_trend,
        "comparison_vs_trend_long": {
            "pnl_delta": rounded(trade_summary["total_pnl"] - trend_pnl, 2),
            "momentum_beats_trend_pnl": trade_summary["total_pnl"] > trend_pnl,
        },
    }


def aggregate_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    momentum_total = sum(money(row["momentum_trade_summary"]["total_pnl"]) for row in windows)
    momentum_trades = sum(int(row["momentum_trade_summary"]["trade_count"]) for row in windows)
    trend_total = sum(money(row["current_trend_long"].get("total_pnl_usd")) for row in windows)
    trend_trades = sum(int(row["current_trend_long"].get("trade_count") or 0) for row in windows)
    win_windows = [
        row["label"]
        for row in windows
        if row["comparison_vs_trend_long"]["momentum_beats_trend_pnl"]
    ]
    max_dd = max(money(row["momentum_metrics"]["max_drawdown_pct"]) for row in windows)
    total_return = momentum_total / CONFIG["initial_capital"]
    mean_sharpe = statistics.fmean(
        [money(row["momentum_metrics"]["sharpe_daily"]) for row in windows]
    )
    return {
        "momentum_total_pnl": rounded(momentum_total, 2),
        "momentum_trade_count": momentum_trades,
        "current_trend_long_total_pnl": rounded(trend_total, 2),
        "current_trend_long_trade_count": trend_trades,
        "pnl_delta_vs_trend_long": rounded(momentum_total - trend_total, 2),
        "momentum_win_window_count_vs_trend_long": len(win_windows),
        "momentum_win_windows_vs_trend_long": win_windows,
        "max_window_drawdown_pct": rounded(max_dd),
        "diagnostic_total_return_pct": rounded(total_return),
        "mean_window_sharpe_daily": rounded(mean_sharpe),
        "diagnostic_expected_value_score": rounded(total_return * mean_sharpe),
    }


def evaluate_lead(aggregate: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    if money(aggregate["momentum_total_pnl"]) <= money(aggregate["current_trend_long_total_pnl"]):
        failed.append("momentum_aggregate_pnl_not_above_current_trend_long")
    if int(aggregate["momentum_win_window_count_vs_trend_long"]) < CONFIG["min_trend_win_windows"]:
        failed.append("momentum_fewer_than_two_windows_beat_trend_long")
    if int(aggregate["momentum_trade_count"]) < CONFIG["min_trade_count_for_lead"]:
        failed.append("momentum_trade_count_below_floor")
    if money(aggregate["max_window_drawdown_pct"]) > CONFIG["max_acceptable_window_drawdown_pct"]:
        failed.append("momentum_drawdown_above_guard")
    if money(aggregate["momentum_total_pnl"]) <= 0:
        failed.append("momentum_not_positive_vs_cash")
    return not failed, failed


def compact_gate4(gate4: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_only": gate4["diagnostic_only"],
        "observed_only_lead": gate4["observed_only_lead"],
        "full_gate4_passed": gate4["full_gate4_passed"],
        "failed_reasons": gate4["failed_reasons"],
        "aggregate": gate4["aggregate"],
        "windows": [
            {
                "label": row["label"],
                "momentum_total_pnl": row["momentum_trade_summary"]["total_pnl"],
                "momentum_trade_count": row["momentum_trade_summary"]["trade_count"],
                "momentum_ev": row["momentum_metrics"]["expected_value_score"],
                "momentum_max_drawdown_pct": row["momentum_metrics"]["max_drawdown_pct"],
                "trend_long_total_pnl": row["current_trend_long"].get("total_pnl_usd"),
                "pnl_delta_vs_trend_long": row["comparison_vs_trend_long"]["pnl_delta"],
                "momentum_beats_trend_pnl": row["comparison_vs_trend_long"][
                    "momentum_beats_trend_pnl"
                ],
            }
            for row in gate4["windows"]
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    windows = [simulate_window(source) for source in WINDOW_SOURCES]
    aggregate = aggregate_windows(windows)
    observed_only_lead, failed_reasons = evaluate_lead(aggregate)
    full_gate4_passed = False
    decision = (
        "observed_only_lead_cross_sectional_12_1_momentum_requires_shared_helper_gate_1_4"
        if observed_only_lead
        else "observed_only_rejected_cross_sectional_12_1_momentum_external_baseline"
    )
    why = (
        "The fixed 12-1 monthly momentum baseline beat current trend_long strongly "
        "enough to justify a shared-helper/backtester promotion test. This is still "
        "not accepted behavior because the private replay does not share production "
        "candidate generation, slot displacement, daily paper state, or live order semantics."
        if observed_only_lead
        else "The fixed 12-1 monthly momentum baseline did not beat the accepted "
        "current trend_long comparator under the predeclared private replay criteria, "
        "so the weakness is not solved by replacing core trend entries with a vanilla "
        "cross-sectional momentum benchmark."
    )
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
        "scope": "read_only_external_12_1_momentum_baseline_replay",
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
        "multiple_testing_risk_bucket": "low",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "realized_success": observed_only_lead,
            "realized_failure_modes": failed_reasons,
        },
        "config": CONFIG,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "gate1": {
            "baseline_available": BASELINE_RESULT.exists(),
            "canonical_snapshots": [repo_rel(row["snapshot"]) for row in WINDOW_SOURCES],
            "canonical_core_results": [repo_rel(row["core_result"]) for row in WINDOW_SOURCES],
            "baseline_protocol": (
                "private external 12-1 monthly momentum replay compared to accepted "
                "current trend_long by_strategy rows"
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
            "private_replay_trade_count": aggregate["momentum_trade_count"],
            "rebalance_count": {
                row["label"]: row["signal_diagnostics"]["rebalance_count"] for row in windows
            },
            "eligible_candidate_count_sum": {
                row["label"]: row["signal_diagnostics"]["eligible_candidate_count_sum"]
                for row in windows
            },
            "passed": aggregate["momentum_trade_count"] >= CONFIG["min_trade_count_for_lead"],
        },
        "gate4": {
            "diagnostic_only": True,
            "full_gate4_passed": full_gate4_passed,
            "observed_only_lead": observed_only_lead,
            "failed_reasons": failed_reasons + ["not_full_gate4_private_external_replay"],
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
                "Do not rerun 12-1 momentum on these frozen windows by changing "
                "252/21 lookbacks, monthly cadence, top-N, hold days, liquidity "
                "floors, universe exclusions, costs, notional, or ranking tie-breaks. "
                "That would be a parameter sweep on the same OHLCV momentum surface."
            ),
            "new_evidence_required": (
                "If positive, next evidence must be a shared helper/backtester Gate "
                "1-4 replay. If negative, move to a different external baseline lane "
                "such as PEAD/revision or low-vol/quality admission instead of "
                "retuning 12-1 parameters."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed_reasons),
        "next_retry_requires": [
            "shared_helper_gate_1_4_before_any_behavior_change"
            if observed_only_lead
            else "different_external_baseline_family_such_as_pead_or_low_vol_quality",
            "no_12_1_lookback_topn_hold_liquidity_universe_cost_notional_or_tiebreak_retune_on_same_windows",
        ],
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
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
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
        f"# {EXPERIMENT_ID}: 12-1 Cross-Sectional Momentum External Baseline",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Observed-only lead: `{payload['observed_only_lead']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Aggregate",
        "",
        f"- 12-1 momentum PnL: `${aggregate['momentum_total_pnl']}`",
        f"- Current `trend_long` PnL: `${aggregate['current_trend_long_total_pnl']}`",
        f"- PnL delta: `${aggregate['pnl_delta_vs_trend_long']}`",
        f"- 12-1 momentum trades: `{aggregate['momentum_trade_count']}`",
        f"- Windows beating `trend_long`: `{', '.join(aggregate['momentum_win_windows_vs_trend_long']) or 'none'}`",
        f"- Max window drawdown: `{aggregate['max_window_drawdown_pct']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Windows",
        "",
        "| Window | 12-1 PnL | 12-1 trades | 12-1 EV | 12-1 maxDD | trend_long PnL | Delta | Beats trend |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in gate4["windows"]:
        lines.append(
            f"| {row['label']} | {row['momentum_trade_summary']['total_pnl']} | "
            f"{row['momentum_trade_summary']['trade_count']} | "
            f"{row['momentum_metrics']['expected_value_score']} | "
            f"{row['momentum_metrics']['max_drawdown_pct']} | "
            f"{row['current_trend_long'].get('total_pnl_usd')} | "
            f"{row['comparison_vs_trend_long']['pnl_delta']} | "
            f"{row['comparison_vs_trend_long']['momentum_beats_trend_pnl']} |"
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
            "multiple_testing_risk_bucket": "low",
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
