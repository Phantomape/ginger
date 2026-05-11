"""Replay SPACE_CATALYST_SHADOW basket diagnostics on augmented OHLCV snapshots.

This is an observe-only diagnostic, not a promotion gate. The current 2026 space
watchlist is replayed on historical windows to estimate theme behavior, with an
explicit look-ahead caveat because the basket itself was selected after those
windows.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260510-028"
INITIAL_CAPITAL = 100_000.0

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/experiments/exp-20260510-028/ohlcv/exp-20260510-028_late_strong_with_space_catalyst.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/experiments/exp-20260510-028/ohlcv/exp-20260510-028_mid_weak_with_space_catalyst.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/experiments/exp-20260510-028/ohlcv/exp-20260510-028_old_thin_with_space_catalyst.json",
    },
}

SPACE_EQUITY_RESEARCH = [
    "RKLB",
    "ASTS",
    "LUNR",
    "HAWK",
    "PL",
    "RDW",
    "BKSY",
    "IRDM",
    "VSAT",
    "GSAT",
    "SATS",
]
SPACE_ETF_PROXIES = ["ARKX", "UFO"]
QUARANTINE = ["SPCE"]
BENCHMARKS = ["SPY", "QQQ", "ARKX", "UFO"]


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("ohlcv")
    if not isinstance(raw, dict):
        raise ValueError(f"snapshot missing ohlcv: {path}")
    return raw


def _close_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    closes: dict[str, float] = {}
    for row in rows or []:
        date = row.get("Date")
        close = row.get("Close")
        if date is None or close is None:
            continue
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            closes[str(date)] = value
    return closes


def _sim_dates(snapshot: dict[str, list[dict[str, Any]]], start: str, end: str) -> list[str]:
    spy = _close_map(snapshot.get("SPY", []))
    return [date for date in sorted(spy) if start <= date <= end]


def _series_for_dates(closes: dict[str, float], dates: list[str]) -> list[float | None]:
    series: list[float | None] = []
    last: float | None = None
    for date in dates:
        if date in closes:
            last = closes[date]
        series.append(last)
    return series


def _metrics(equity_curve: list[float]) -> dict[str, Any]:
    if len(equity_curve) < 2:
        return {
            "total_return_pct": 0.0,
            "total_pnl": 0.0,
            "sharpe_daily": 0.0,
            "expected_value_score": 0.0,
            "max_drawdown_pct": 0.0,
            "daily_observations": len(equity_curve),
        }
    daily_returns = [
        equity_curve[idx] / equity_curve[idx - 1] - 1.0
        for idx in range(1, len(equity_curve))
        if equity_curve[idx - 1] > 0
    ]
    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    std = pstdev(daily_returns) if len(daily_returns) > 1 else 0.0
    sharpe = (mean(daily_returns) / std * math.sqrt(252)) if std else 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            max_dd = min(max_dd, value / peak - 1.0)
    return {
        "total_return_pct": round(total_return, 6),
        "total_pnl": round((equity_curve[-1] - equity_curve[0]), 2),
        "sharpe_daily": round(sharpe, 4),
        "expected_value_score": round(total_return * sharpe, 4),
        "max_drawdown_pct": round(abs(max_dd), 6),
        "daily_observations": len(equity_curve),
    }


def _buy_hold_replay(
    snapshot: dict[str, list[dict[str, Any]]],
    tickers: list[str],
    dates: list[str],
) -> dict[str, Any]:
    included: list[str] = []
    missing: list[str] = []
    series_by_ticker: dict[str, list[float | None]] = {}
    for ticker in tickers:
        series = _series_for_dates(_close_map(snapshot.get(ticker, [])), dates)
        if not series or series[0] is None or series[-1] is None:
            missing.append(ticker)
            continue
        included.append(ticker)
        series_by_ticker[ticker] = series

    if not included:
        return {"included_tickers": [], "missing_tickers": missing, **_metrics([INITIAL_CAPITAL])}

    weight = 1.0 / len(included)
    equity_curve: list[float] = []
    ticker_returns: dict[str, float] = {}
    for idx, _date in enumerate(dates):
        normalized_values = []
        for ticker in included:
            series = series_by_ticker[ticker]
            entry = series[0]
            current = series[idx]
            if entry is None or current is None:
                normalized_values.append(1.0)
            else:
                normalized_values.append(current / entry)
        equity_curve.append(INITIAL_CAPITAL * sum(value * weight for value in normalized_values))

    contributions: dict[str, float] = {}
    for ticker in included:
        series = series_by_ticker[ticker]
        ticker_return = (series[-1] / series[0] - 1.0) if series[0] and series[-1] else 0.0
        ticker_returns[ticker] = round(ticker_return, 6)
        contributions[ticker] = round(INITIAL_CAPITAL * weight * ticker_return, 2)
    positive_contrib = {ticker: pnl for ticker, pnl in contributions.items() if pnl > 0}
    positive_sum = sum(positive_contrib.values())
    top_positive_share = (
        max(positive_contrib.values()) / positive_sum if positive_sum > 0 else 0.0
    )

    result = _metrics(equity_curve)
    result.update(
        {
            "included_tickers": included,
            "missing_tickers": missing,
            "ticker_returns": ticker_returns,
            "pnl_contribution": contributions,
            "max_single_positive_contribution_share": round(top_positive_share, 4),
        }
    )
    return result


def _momentum_top3_replay(
    snapshot: dict[str, list[dict[str, Any]]],
    tickers: list[str],
    dates: list[str],
    lookback_days: int = 20,
    rebalance_every: int = 20,
    top_n: int = 3,
) -> dict[str, Any]:
    close_maps = {ticker: _close_map(snapshot.get(ticker, [])) for ticker in tickers}
    all_dates_by_ticker = {ticker: sorted(closes) for ticker, closes in close_maps.items()}
    holdings: list[str] = []
    equity_curve = [INITIAL_CAPITAL]
    selection_history: list[dict[str, Any]] = []

    def select(as_of: str) -> list[str]:
        scores: list[tuple[float, str]] = []
        for ticker, closes in close_maps.items():
            ticker_dates = [date for date in all_dates_by_ticker[ticker] if date <= as_of]
            if len(ticker_dates) <= lookback_days:
                continue
            now = ticker_dates[-1]
            then = ticker_dates[-1 - lookback_days]
            if closes[then] <= 0:
                continue
            scores.append((closes[now] / closes[then] - 1.0, ticker))
        scores.sort(reverse=True)
        return [ticker for _score, ticker in scores[:top_n]]

    if dates:
        holdings = select(dates[0])
        selection_history.append({"date": dates[0], "selected": holdings})

    for idx in range(1, len(dates)):
        prev_date = dates[idx - 1]
        date = dates[idx]
        if holdings:
            returns = []
            for ticker in holdings:
                closes = close_maps[ticker]
                prev = closes.get(prev_date)
                current = closes.get(date)
                if prev and current:
                    returns.append(current / prev - 1.0)
            daily_return = mean(returns) if returns else 0.0
        else:
            daily_return = 0.0
        equity_curve.append(equity_curve[-1] * (1.0 + daily_return))
        if idx % rebalance_every == 0:
            holdings = select(date)
            selection_history.append({"date": date, "selected": holdings})

    result = _metrics(equity_curve)
    flat_counts: dict[str, int] = {}
    for event in selection_history:
        for ticker in event["selected"]:
            flat_counts[ticker] = flat_counts.get(ticker, 0) + 1
    result.update(
        {
            "lookback_days": lookback_days,
            "rebalance_every_trading_days": rebalance_every,
            "top_n": top_n,
            "selection_count_by_ticker": dict(sorted(flat_counts.items())),
            "selection_history": selection_history,
            "cost_model": "none",
        }
    )
    return result


def run_replay() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "change_type": "observe_only_space_catalyst_shadow_replay",
        "changed_variable": "current_space_shadow_basket_historical_replay",
        "initial_capital": INITIAL_CAPITAL,
        "lookahead_caveat": (
            "The current 2026-05-10 space catalyst basket is applied to older windows. "
            "Use this as a theme-risk diagnostic, not as acceptance evidence for live trading."
        ),
        "windows": {},
    }
    for label, spec in WINDOWS.items():
        snapshot = _load_snapshot(REPO_ROOT / spec["snapshot"])
        dates = _sim_dates(snapshot, spec["start"], spec["end"])
        equity_tickers = SPACE_EQUITY_RESEARCH
        research_plus_etfs = SPACE_EQUITY_RESEARCH + SPACE_ETF_PROXIES
        payload["windows"][label] = {
            "date_range": f"{spec['start']} -> {spec['end']}",
            "snapshot": spec["snapshot"],
            "space_equity_equal_weight": _buy_hold_replay(snapshot, equity_tickers, dates),
            "space_research_plus_etfs_equal_weight": _buy_hold_replay(
                snapshot,
                research_plus_etfs,
                dates,
            ),
            "space_equity_top3_rs20_monthly": _momentum_top3_replay(
                snapshot,
                equity_tickers,
                dates,
            ),
            "quarantine_spce_buy_hold": _buy_hold_replay(snapshot, QUARANTINE, dates),
            "benchmarks": {
                ticker: _buy_hold_replay(snapshot, [ticker], dates)
                for ticker in BENCHMARKS
            },
        }
    return payload


def main() -> None:
    payload = run_replay()
    output = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / "space_catalyst_shadow_basket_replay.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
