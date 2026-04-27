"""Audit entry-extension failure families without changing strategy behavior."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "quant"))
from yfinance_bootstrap import configure_yfinance_runtime  # noqa: E402

configure_yfinance_runtime()


def _load_backtest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    return value


def _download_history(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a / b) - 1.0


def _entry_features(df: pd.DataFrame, entry_date: str, entry_price: float) -> dict:
    if df.empty:
        return {"data_status": "missing_history"}

    frame = df.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    entry_ts = pd.to_datetime(entry_date)
    prior = frame[frame.index <= entry_ts].tail(80)
    if len(prior) < 25:
        return {"data_status": "insufficient_history", "history_rows": len(prior)}

    closes = prior["Close"].astype(float)
    latest_close = _as_float(closes.iloc[-1])
    high_20 = _as_float(prior["High"].astype(float).tail(20).max())
    low_20 = _as_float(prior["Low"].astype(float).tail(20).min())

    def trailing_return(days: int):
        if len(closes) <= days:
            return None
        return _pct(latest_close, _as_float(closes.iloc[-days - 1]))

    sma10 = _as_float(closes.tail(10).mean())
    sma20 = _as_float(closes.tail(20).mean())
    sma50 = _as_float(closes.tail(50).mean()) if len(closes) >= 50 else None
    range_pos_20d = None
    if high_20 is not None and low_20 is not None and high_20 > low_20:
        range_pos_20d = (entry_price - low_20) / (high_20 - low_20)

    close_vs_sma10 = _pct(entry_price, sma10)
    close_vs_sma20 = _pct(entry_price, sma20)
    close_vs_sma50 = _pct(entry_price, sma50)
    ret_5d = trailing_return(5)
    ret_10d = trailing_return(10)
    ret_20d = trailing_return(20)

    extension_flags = {
        "entry_ge_8pct_above_sma20": close_vs_sma20 is not None and close_vs_sma20 >= 0.08,
        "entry_ge_12pct_prior_10d": ret_10d is not None and ret_10d >= 0.12,
        "entry_top_5pct_20d_and_above_sma10": (
            range_pos_20d is not None
            and close_vs_sma10 is not None
            and range_pos_20d >= 0.95
            and close_vs_sma10 >= 0.04
        ),
    }
    extended_entry = any(extension_flags.values())

    return {
        "data_status": "ok",
        "history_rows": len(prior),
        "entry_price": entry_price,
        "latest_close": latest_close,
        "close_vs_sma10": close_vs_sma10,
        "close_vs_sma20": close_vs_sma20,
        "close_vs_sma50": close_vs_sma50,
        "prior_5d_return": ret_5d,
        "prior_10d_return": ret_10d,
        "prior_20d_return": ret_20d,
        "range_pos_20d": range_pos_20d,
        "extension_flags": extension_flags,
        "extended_entry": extended_entry,
    }


def _summarize(records: list[dict], baseline: dict, experiment_id: str) -> dict:
    ok = [r for r in records if r["features"].get("data_status") == "ok"]
    losses = [r for r in ok if r["is_loss"]]
    wins = [r for r in ok if not r["is_loss"]]
    extended_losses = [r for r in losses if r["features"].get("extended_entry")]
    extended_wins = [r for r in wins if r["features"].get("extended_entry")]

    flag_counts = defaultdict(Counter)
    for r in ok:
        group = "loss" if r["is_loss"] else "win"
        for flag, enabled in r["features"].get("extension_flags", {}).items():
            if enabled:
                flag_counts[group][flag] += 1

    by_strategy = defaultdict(lambda: {"total": 0, "losses": 0, "extended_losses": 0, "extended_wins": 0})
    for r in ok:
        bucket = by_strategy[r["strategy"]]
        bucket["total"] += 1
        if r["is_loss"]:
            bucket["losses"] += 1
            if r["features"].get("extended_entry"):
                bucket["extended_losses"] += 1
        elif r["features"].get("extended_entry"):
            bucket["extended_wins"] += 1

    collateral_pnl = sum(_as_float(r["pnl"]) or 0.0 for r in extended_wins)
    avoided_loss_pnl = sum(_as_float(r["pnl"]) or 0.0 for r in extended_losses)
    net_naive_filter_delta = -avoided_loss_pnl - collateral_pnl

    return {
        "experiment_id": experiment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_backtest": {
            "period": baseline.get("period"),
            "total_trades": baseline.get("total_trades"),
            "wins": baseline.get("wins"),
            "losses": baseline.get("losses"),
            "expected_value_score": baseline.get("expected_value_score"),
            "sharpe_daily": baseline.get("sharpe_daily"),
            "max_drawdown_pct": baseline.get("max_drawdown_pct"),
        },
        "taxonomy": {
            "family": "entry_short_term_extension_failure",
            "definition": (
                "Loss trade with entry >=8% above SMA20, or prior 10d return >=12%, "
                "or top 5% of 20d range while >=4% above SMA10."
            ),
            "total_audited_with_history": len(ok),
            "losses_with_history": len(losses),
            "wins_with_history": len(wins),
            "extended_losses": len(extended_losses),
            "extended_wins": len(extended_wins),
            "loss_coverage_rate": len(extended_losses) / len(losses) if losses else 0.0,
            "winner_collateral_rate": len(extended_wins) / len(wins) if wins else 0.0,
            "flag_counts": {k: dict(v) for k, v in flag_counts.items()},
            "by_strategy": dict(by_strategy),
        },
        "collateral_risk_estimate": {
            "extended_winner_count": len(extended_wins),
            "extended_winner_pnl_at_risk": round(collateral_pnl, 2),
            "extended_loss_count": len(extended_losses),
            "extended_loss_pnl_that_naive_filter_would_avoid": round(-avoided_loss_pnl, 2),
            "naive_filter_net_pnl_delta_estimate": round(net_naive_filter_delta, 2),
            "interpretation": (
                "Positive delta would support a future narrow alpha/risk experiment; "
                "negative delta means a naive extension filter would likely remove more winner PnL than loss PnL."
            ),
        },
        "next_alpha_candidate": {
            "candidate": "Do not add a broad entry-extension filter. If pursued, test a narrow shadow ranking penalty only where extension coincides with weak next-day follow-through.",
            "blocked_by": "This audit is observational; it has not replayed strategy behavior, slot competition, or exits.",
        },
        "records": records,
    }


def run(args) -> dict:
    baseline = _load_backtest(Path(args.backtest))
    trades = baseline.get("trades", [])
    if not trades:
        raise SystemExit(f"No trades found in {args.backtest}")

    by_ticker_dates = defaultdict(list)
    for trade in trades:
        entry_date = trade.get("entry_date")
        ticker = trade.get("ticker")
        if ticker and entry_date:
            by_ticker_dates[ticker].append(pd.to_datetime(entry_date))

    histories = {}
    for ticker, dates in by_ticker_dates.items():
        start = (min(dates) - timedelta(days=args.lookback_calendar_days)).date().isoformat()
        end = (max(dates) + timedelta(days=5)).date().isoformat()
        histories[ticker] = _download_history(ticker, start, end)

    records = []
    for trade in trades:
        ticker = trade.get("ticker")
        entry_date = trade.get("entry_date")
        entry_price = _as_float(trade.get("entry_price"))
        if not ticker or not entry_date or entry_price is None:
            features = {"data_status": "missing_trade_entry_fields"}
        else:
            features = _entry_features(histories.get(ticker, pd.DataFrame()), entry_date, entry_price)
        records.append(
            {
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _as_float(trade.get("pnl")),
                "pnl_pct_net": _as_float(trade.get("pnl_pct_net")),
                "is_loss": (_as_float(trade.get("pnl")) or 0.0) < 0,
                "features": features,
            }
        )

    result = _summarize(records, baseline, args.experiment_id)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", default="exp-20260427-012")
    parser.add_argument("--backtest", default="data/backtest_results_20260426.json")
    parser.add_argument("--output", default="data/entry_extension_failure_audit_exp-20260427-012.json")
    parser.add_argument("--lookback-calendar-days", type=int, default=140)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result["taxonomy"], indent=2, sort_keys=True))
    print(json.dumps(result["collateral_risk_estimate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
