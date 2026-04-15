"""
Signal-Level Backtester — replays historical OHLCV through the ACTUAL pipeline.

Unlike the previous simplified breakout heuristic, this backtester calls the
real signal_engine.generate_signals() + risk_engine.enrich_signals() + all
filter layers from run.py.  It assumes every signal that survives the full
pipeline is executed at next-day open (with exec_lag), and tracks positions
using the signal's stop_price and target_price.

Strategy C (earnings) is excluded because historical earnings dates are
unreliable via yfinance.  Only Strategy A (trend) and B (breakout) are tested.

Usage:
    cd d:/Github/ginger
    python quant/backtester.py                        # default 6-month backtest
    python quant/backtester.py --start 2025-06-01 --end 2025-12-31
    python quant/backtester.py --sweep ATR_STOP_MULT 1.0 1.5 2.0
"""

import json
import logging
import math
import os
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "INITIAL_CAPITAL":     100_000.0,
    "MAX_POSITIONS":       5,
    "LOOKBACK_CALENDAR_DAYS": 400,   # enough for 200-day MA + features
}


class Position:
    """Track a single open backtested position."""

    __slots__ = ("ticker", "entry_price", "entry_open_price", "stop_price",
                 "target_price", "shares", "entry_date", "strategy", "sector")

    def __init__(self, ticker, entry_price, stop_price, target_price,
                 shares, entry_date, strategy, sector="Unknown",
                 entry_open_price=None):
        self.ticker           = ticker
        self.entry_price      = entry_price               # post-slippage fill
        self.entry_open_price = entry_open_price or entry_price
        self.stop_price       = stop_price
        self.target_price     = target_price
        self.shares           = shares
        self.entry_date       = entry_date
        self.strategy         = strategy
        self.sector           = sector


class BacktestEngine:
    """
    Walk-forward backtester using the real signal pipeline.

    Args:
        universe   (list[str]): Ticker symbols to test
        start      (str):       Start date YYYY-MM-DD
        end        (str):       End date YYYY-MM-DD
        config     (dict):      Override any key in DEFAULT_CONFIG
    """

    def __init__(self, universe, start=None, end=None, config=None):
        self.universe = universe
        self.config   = {**DEFAULT_CONFIG, **(config or {})}
        self.start    = pd.Timestamp(start) if start else None
        self.end      = pd.Timestamp(end)   if end   else None

    def _download_data(self):
        """Download OHLCV for universe + SPY + QQQ."""
        all_tickers = list(set(self.universe + ["SPY", "QQQ"]))
        lookback = self.config["LOOKBACK_CALENDAR_DAYS"]

        # Determine download range: we need lookback days BEFORE start
        if self.end:
            dl_end = self.end + pd.Timedelta(days=5)  # buffer for next-day fill
        else:
            dl_end = pd.Timestamp.now()

        if self.start:
            dl_start = self.start - pd.Timedelta(days=lookback)
        else:
            dl_start = dl_end - pd.Timedelta(days=lookback + 180)

        logger.info(f"Downloading {len(all_tickers)} tickers: "
                    f"{dl_start.date()} → {dl_end.date()}")

        ohlcv = {}
        for ticker in all_tickers:
            try:
                df = yf.download(ticker, start=dl_start, end=dl_end,
                                 progress=False)
                if df is not None and not df.empty:
                    # Flatten multi-level columns if present
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    ohlcv[ticker] = df
                    logger.info(f"  {ticker}: {len(df)} rows")
                else:
                    logger.warning(f"  {ticker}: no data")
            except Exception as e:
                logger.warning(f"  {ticker}: download failed — {e}")

        return ohlcv

    def run(self):
        """
        Execute the backtest.

        Returns:
            dict: {total_trades, wins, losses, win_rate, total_pnl, sharpe,
                   max_drawdown_pct, equity_curve, trades, signals_generated,
                   signals_survived, survival_rate}
        """
        from feature_layer    import compute_features
        from signal_engine    import generate_signals
        from risk_engine      import enrich_signals
        from portfolio_engine import size_signals, ROUND_TRIP_COST_PCT
        from regime           import compute_market_regime
        from fill_model       import (
            apply_entry_fill, apply_stop_fill, apply_target_fill,
            apply_slippage,   SLIPPAGE_BPS_TARGET,
        )

        ohlcv_all = self._download_data()
        if not ohlcv_all:
            return {"error": "No data downloaded"}

        # Build unified trading-day index from SPY
        spy_df = ohlcv_all.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data unavailable — cannot determine trading days"}

        all_dates = sorted(spy_df.index)
        if self.start:
            sim_dates = [d for d in all_dates if d >= self.start]
        else:
            sim_dates = all_dates[-126:]  # default: last ~6 months
        if self.end:
            sim_dates = [d for d in sim_dates if d <= self.end]

        if len(sim_dates) < 2:
            return {"error": "Insufficient simulation dates"}

        logger.info(f"Simulating {len(sim_dates)} trading days: "
                    f"{sim_dates[0].date()} → {sim_dates[-1].date()}")

        # State
        capital       = self.config["INITIAL_CAPITAL"]
        equity        = capital
        positions     = []          # list[Position]
        closed        = []          # list[dict]
        equity_curve  = []
        total_signals_generated = 0
        total_signals_survived  = 0

        for day_idx, today in enumerate(sim_dates):

            # ── 1. Check exits on today's prices ────────────────────────────
            still_open = []
            for pos in positions:
                df = ohlcv_all.get(pos.ticker)
                if df is None or today not in df.index:
                    still_open.append(pos)
                    continue

                row = df.loc[today]
                opn  = float(row["Open"].item()  if hasattr(row["Open"],  "item") else row["Open"])
                low  = float(row["Low"].item()   if hasattr(row["Low"],   "item") else row["Low"])
                high = float(row["High"].item()  if hasattr(row["High"],  "item") else row["High"])

                exit_price    = None      # slippage-adjusted fill
                exit_raw_price = None     # theoretical trigger level (pre-slippage)
                exit_reason   = None

                # Stop hit (gap-fill or intraday) — sell slippage on top.
                if pos.stop_price and low <= pos.stop_price:
                    exit_raw_price = opn if opn < pos.stop_price else pos.stop_price
                    exit_price     = apply_stop_fill(opn, pos.stop_price)
                    exit_reason    = "stop"
                # Target hit — gap-up uses Open (bonus), intraday uses target; slippage on top.
                elif pos.target_price and high >= pos.target_price:
                    exit_raw_price = opn if opn >= pos.target_price else pos.target_price
                    exit_price     = apply_target_fill(opn, pos.target_price)
                    exit_reason    = "target"

                if exit_price is not None:
                    cost = exit_price * ROUND_TRIP_COST_PCT * pos.shares
                    pnl  = (exit_price - pos.entry_price) * pos.shares - cost
                    equity += pnl
                    # Entry-side slippage dollars were already baked into
                    # pos.entry_price at open time, but the raw Open was stored
                    # on Position so we can surface total slippage_cost here.
                    entry_slip = (pos.entry_price - pos.entry_open_price) * pos.shares
                    exit_slip  = (exit_raw_price  - exit_price)           * pos.shares
                    pnl_pct_net = ((exit_price - pos.entry_price) / pos.entry_price
                                   - ROUND_TRIP_COST_PCT)
                    initial_risk_pct = (((pos.entry_price - pos.stop_price) / pos.entry_price)
                                        if pos.stop_price and pos.entry_price else None)
                    closed.append({
                        "ticker":           pos.ticker,
                        "strategy":         pos.strategy,
                        "sector":           pos.sector,
                        "entry_price":      pos.entry_price,
                        "entry_open_price": pos.entry_open_price,        # raw next-day Open
                        "stop_price":       pos.stop_price,
                        "exit_price":       round(exit_price, 2),        # after slippage
                        "exit_raw_price":   round(exit_raw_price, 4),    # pre-slippage trigger
                        "shares":           pos.shares,
                        "pnl":              round(pnl, 2),
                        "pnl_pct_net":      round(pnl_pct_net, 6),
                        "initial_risk_pct": round(initial_risk_pct, 6) if initial_risk_pct else None,
                        "slippage_cost":    round(entry_slip + exit_slip, 2),
                        "exit_reason":      exit_reason,
                        "entry_date":  str(pos.entry_date.date()) if hasattr(pos.entry_date, "date") else str(pos.entry_date),
                        "exit_date":   str(today.date()) if hasattr(today, "date") else str(today),
                    })
                else:
                    still_open.append(pos)

            positions = still_open

            # ── 2. Generate signals using the REAL pipeline ─────────────────
            # Skip if at max positions
            if len(positions) >= self.config["MAX_POSITIONS"]:
                equity_curve.append((str(today.date()), round(equity, 2)))
                continue

            # Compute features for each ticker using data up to today
            features_dict = {}
            for ticker in self.universe:
                df = ohlcv_all.get(ticker)
                if df is None:
                    continue
                # Slice up to today (inclusive) — no future data
                data_slice = df.loc[:today]
                if len(data_slice) < 21:
                    continue
                features_dict[ticker] = compute_features(ticker, data_slice, None)

            # Compute market regime from historical SPY/QQQ
            regime_ohlcv = {}
            for idx_ticker in ["SPY", "QQQ"]:
                df = ohlcv_all.get(idx_ticker)
                if df is not None:
                    regime_ohlcv[idx_ticker] = df.loc[:today]

            regime_result = compute_market_regime(ohlcv_override=regime_ohlcv)
            regime_str    = regime_result.get("regime", "UNKNOWN")
            spy_pct       = regime_result.get("indices", {}).get("SPY", {}).get("pct_from_ma")
            qqq_pct       = regime_result.get("indices", {}).get("QQQ", {}).get("pct_from_ma")
            spy_10d       = regime_result.get("indices", {}).get("SPY", {}).get("momentum_10d_pct")

            market_context = {
                "market_regime":   regime_str,
                "spy_10d_return":  spy_10d,
                "spy_pct_from_ma": spy_pct,
                "qqq_pct_from_ma": qqq_pct,
            }

            # Generate signals (Strategy A + B; C skipped because earnings=None)
            signals = generate_signals(features_dict, market_context=market_context)
            total_signals_generated += len(signals)

            # Enrich with risk parameters
            signals = enrich_signals(signals, features_dict)

            # Sector concentration cap (same as run.py)
            _MAX_PER_SECTOR = 2
            _sector_counts = {}
            _capped = []
            for s in signals:
                sec = s.get("sector", "Unknown")
                _sector_counts[sec] = _sector_counts.get(sec, 0) + 1
                if _sector_counts[sec] <= _MAX_PER_SECTOR:
                    _capped.append(s)
            signals = _capped

            # BEAR_SHALLOW post-enrich filter (same as run.py)
            if (regime_str == "BEAR"
                    and spy_pct is not None and qqq_pct is not None
                    and min(spy_pct, qqq_pct) > -0.05):
                signals = [
                    s for s in signals
                    if s.get("sector") in {"Commodities", "Healthcare"}
                    and (s.get("trade_quality_score") or 0) >= 0.75
                ]

            # Regime-adjusted risk per trade
            if regime_str == "NEUTRAL":
                risk_pct = 0.0075
            elif (regime_str == "BEAR"
                  and spy_pct is not None and qqq_pct is not None
                  and min(spy_pct, qqq_pct) > -0.05):
                risk_pct = 0.005
            else:
                risk_pct = None  # default 1%

            # Size signals
            signals = size_signals(signals, equity, risk_pct=risk_pct)
            total_signals_survived += len(signals)

            # ── 3. Enter positions at next-day open ─────────────────────────
            slots = self.config["MAX_POSITIONS"] - len(positions)
            for sig in signals[:slots]:
                ticker = sig["ticker"]
                # Skip if already holding
                if any(p.ticker == ticker for p in positions):
                    continue

                sizing = sig.get("sizing")
                if not sizing or not sizing.get("shares_to_buy"):
                    continue

                shares = sizing["shares_to_buy"]
                stop   = sig.get("stop_price")
                target = sig.get("target_price")

                if not stop or not target:
                    continue

                # Fill at next-day open
                df = ohlcv_all.get(ticker)
                if df is None:
                    continue

                future_dates = [d for d in all_dates if d > today]
                fill_price = None
                fill_date  = None
                for nd in future_dates[:3]:  # look ahead up to 3 days for fill
                    if nd in df.index:
                        fill_row = df.loc[nd]
                        fill_price = float(
                            fill_row["Open"].item()
                            if hasattr(fill_row["Open"], "item")
                            else fill_row["Open"]
                        )
                        fill_date = nd
                        break

                if fill_price is None:
                    continue

                # Cancel if gap too large (>1.5% above signal entry).
                # The gap check uses the RAW Open (not slippage-adjusted) so the
                # cancel boundary is determined by market conditions, not by our
                # own execution-cost assumptions.
                signal_entry = sig.get("entry_price", fill_price)
                if fill_price > signal_entry * 1.015:
                    continue

                entry_fill = apply_entry_fill(fill_price)   # buy-side slippage
                positions.append(Position(
                    ticker=ticker,
                    entry_price=round(entry_fill, 2),
                    entry_open_price=round(fill_price, 4),  # raw next-day Open
                    stop_price=stop,
                    target_price=target,
                    shares=shares,
                    entry_date=fill_date,
                    strategy=sig.get("strategy", "unknown"),
                    sector=sig.get("sector", "Unknown"),
                ))

            # Mark-to-market equity
            mtm = capital
            for t in closed:
                mtm += t["pnl"]  # realized
            for pos in positions:
                df = ohlcv_all.get(pos.ticker)
                if df is not None and today in df.index:
                    row = df.loc[today]
                    cls = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
                    mtm += (cls - pos.entry_price) * pos.shares
                # If no price, unrealized = 0

            equity_curve.append((str(today.date()), round(mtm, 2)))

        # ── Force-close remaining positions at last day's close ─────────────
        last_day = sim_dates[-1]
        for pos in positions:
            df = ohlcv_all.get(pos.ticker)
            if df is not None and last_day in df.index:
                row = df.loc[last_day]
                raw_close  = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
                # Use target-side slippage budget (5 bps) — this is a mark-to-market
                # unwind, not an adverse stop, so the stop-impact model would be
                # too pessimistic.
                exit_price = apply_slippage(raw_close, SLIPPAGE_BPS_TARGET, "sell")
                exit_raw_price = raw_close
            else:
                exit_price = pos.entry_price     # flat — no price data
                exit_raw_price = pos.entry_price

            cost = exit_price * ROUND_TRIP_COST_PCT * pos.shares
            pnl  = (exit_price - pos.entry_price) * pos.shares - cost
            equity += pnl
            entry_slip = (pos.entry_price - pos.entry_open_price) * pos.shares
            exit_slip  = (exit_raw_price  - exit_price)           * pos.shares
            pnl_pct_net = ((exit_price - pos.entry_price) / pos.entry_price
                           - ROUND_TRIP_COST_PCT)
            initial_risk_pct = (((pos.entry_price - pos.stop_price) / pos.entry_price)
                                if pos.stop_price and pos.entry_price else None)
            closed.append({
                "ticker":           pos.ticker,
                "strategy":         pos.strategy,
                "sector":           pos.sector,
                "entry_price":      pos.entry_price,
                "entry_open_price": pos.entry_open_price,
                "stop_price":       pos.stop_price,
                "exit_price":       round(exit_price, 2),
                "exit_raw_price":   round(exit_raw_price, 4),
                "shares":           pos.shares,
                "pnl":              round(pnl, 2),
                "pnl_pct_net":      round(pnl_pct_net, 6),
                "initial_risk_pct": round(initial_risk_pct, 6) if initial_risk_pct else None,
                "slippage_cost":    round(entry_slip + exit_slip, 2),
                "exit_reason":      "end_of_backtest",
                "entry_date":  str(pos.entry_date.date()) if hasattr(pos.entry_date, "date") else str(pos.entry_date),
                "exit_date":   str(last_day.date()),
            })

        # ── Compute metrics ─────────────────────────────────────────────────
        wins   = [t for t in closed if t["pnl"] > 0]
        losses = [t for t in closed if t["pnl"] <= 0]
        total  = len(closed)

        # Max drawdown from equity curve
        peak   = 0.0
        max_dd = 0.0
        for _, eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Sharpe from trade P&L (annualized assuming ~30 trades/year)
        pnl_series = [t["pnl"] for t in closed]
        if len(pnl_series) >= 2:
            mean_pnl = sum(pnl_series) / len(pnl_series)
            var_pnl  = sum((x - mean_pnl) ** 2 for x in pnl_series) / (len(pnl_series) - 1)
            std_pnl  = math.sqrt(var_pnl) if var_pnl > 0 else 0
            sharpe   = round((mean_pnl / std_pnl) * math.sqrt(30), 2) if std_pnl > 0 else None
        else:
            sharpe = None

        survival_rate = (round(total_signals_survived / total_signals_generated, 4)
                         if total_signals_generated > 0 else 0)

        from strategy_attribution import aggregate_by_strategy
        by_strategy = aggregate_by_strategy([
            {**t, "pnl_usd": t["pnl"]} for t in closed
        ])

        return {
            "period":              f"{sim_dates[0].date()} → {sim_dates[-1].date()}",
            "trading_days":        len(sim_dates),
            "total_trades":        total,
            "wins":                len(wins),
            "losses":              len(losses),
            "win_rate":            round(len(wins) / total, 4) if total else 0,
            "total_pnl":           round(sum(t["pnl"] for t in closed), 2),
            "sharpe":              sharpe,
            "max_drawdown_pct":    round(max_dd, 4),
            "signals_generated":   total_signals_generated,
            "signals_survived":    total_signals_survived,
            "survival_rate":       survival_rate,
            "by_strategy":         by_strategy,
            "equity_curve":        equity_curve,
            "trades":              closed,
        }

    def sweep(self, param_name, values):
        """
        Single-parameter sweep: varies a config key across values.

        Currently supports MAX_POSITIONS and INITIAL_CAPITAL.
        For signal engine parameters (ATR multipliers etc.), modify the
        source module constants before running — this backtester calls them
        directly rather than passing config overrides.

        Returns:
            list[dict]: One result dict per value
        """
        results = []
        for val in values:
            cfg = {**self.config, param_name: val}
            engine = BacktestEngine(
                self.universe,
                start=str(self.start.date()) if self.start else None,
                end=str(self.end.date()) if self.end else None,
                config=cfg,
            )
            result = engine.run()
            result["param_name"]  = param_name
            result["param_value"] = val
            results.append(result)
            logger.info(
                f"Sweep {param_name}={val}: trades={result.get('total_trades', 0)} "
                f"pnl={result.get('total_pnl', 0):.2f} sharpe={result.get('sharpe')}"
            )
        return results


# ── CLI ─────────────────────────────────────────────────────────────────────

def _print_results(results):
    """Pretty-print backtest results to console."""
    print("\n" + "=" * 60)
    print("  SIGNAL-LEVEL BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Period:            {results['period']}")
    print(f"  Trading days:      {results['trading_days']}")
    print(f"  Total trades:      {results['total_trades']}")
    print(f"  Wins / Losses:     {results['wins']} / {results['losses']}")
    print(f"  Win rate:          {results['win_rate']*100:.1f}%")
    print(f"  Total PnL:         ${results['total_pnl']:,.2f}")
    print(f"  Sharpe:            {results['sharpe']}")
    print(f"  Max drawdown:      {results['max_drawdown_pct']*100:.2f}%")
    print(f"  Signals generated: {results['signals_generated']}")
    print(f"  Signals survived:  {results['signals_survived']}")
    print(f"  Survival rate:     {results['survival_rate']*100:.1f}%")
    print("=" * 60)

    if results.get("by_strategy"):
        from strategy_attribution import format_attribution_table
        print("\n  PER-STRATEGY ATTRIBUTION:")
        print(format_attribution_table(results["by_strategy"]))

    if results.get("trades"):
        print("\n  TRADE LOG:")
        print(f"  {'Ticker':<8} {'Strategy':<20} {'Entry':>8} {'Exit':>8} "
              f"{'PnL':>10} {'Reason':<12} {'Dates'}")
        print("  " + "-" * 90)
        for t in results["trades"]:
            print(f"  {t['ticker']:<8} {t['strategy']:<20} "
                  f"${t['entry_price']:>7.2f} ${t['exit_price']:>7.2f} "
                  f"${t['pnl']:>9.2f} {t['exit_reason']:<12} "
                  f"{t['entry_date']} → {t['exit_date']}")
    print()


def main():
    import argparse

    # Ensure quant/ is on sys.path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Signal-level backtester")
    parser.add_argument("--start", type=str, default=None,
                        help="Start date YYYY-MM-DD (default: 6 months ago)")
    parser.add_argument("--end", type=str, default=None,
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--sweep", nargs="+", default=None,
                        help="Parameter sweep: PARAM_NAME val1 val2 ...")
    args = parser.parse_args()

    # Default: last 6 months
    if not args.start:
        args.start = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime("%Y-%m-%d")
    if not args.end:
        args.end = pd.Timestamp.now().strftime("%Y-%m-%d")

    # Universe from data_layer
    try:
        from data_layer import get_universe
        universe = get_universe()
    except Exception:
        from filter import WATCHLIST
        universe = list(WATCHLIST)

    engine = BacktestEngine(universe, start=args.start, end=args.end)

    if args.sweep and len(args.sweep) >= 2:
        param_name = args.sweep[0]
        values = [float(v) for v in args.sweep[1:]]
        results_list = engine.sweep(param_name, values)
        for r in results_list:
            print(f"\n--- {param_name} = {r['param_value']} ---")
            _print_results(r)
    else:
        results = engine.run()

        if "error" in results:
            print(f"ERROR: {results['error']}")
            sys.exit(1)

        _print_results(results)

        # Save results
        out_path = os.path.join(script_dir, "..", "data",
                                f"backtest_results_{datetime.now().strftime('%Y%m%d')}.json")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

        save_data = {k: v for k, v in results.items() if k != "equity_curve"}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        print(f"Results saved → {out_path}")


if __name__ == "__main__":
    main()
