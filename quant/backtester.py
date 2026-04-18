"""
Signal-Level Backtester — replays historical OHLCV through the ACTUAL pipeline.

Unlike the previous simplified breakout heuristic, this backtester calls the
real signal_engine.generate_signals() + risk_engine.enrich_signals() + all
quant filter layers from run.py.  It assumes every signal that survives the
pipeline is executed at next-day open (with exec_lag), and tracks positions
using the signal's stop_price and target_price.

Strategy C (earnings) is excluded because historical earnings dates are
unreliable via yfinance.  Only Strategy A (trend) and B (breakout) are tested.

KNOWN PARITY GAP — news veto layer:
    Production (`run.py`) applies a T1-negative-news veto via filter.py
    (EVENT_KEYWORDS, T1_TITLE_KEYWORDS).  We have no historical news archive
    to replay, so signals that production rejected on news grounds will be
    accepted in backtest.  Empirically this inflates win rate / total return
    by an unknown but non-zero margin.  Treat backtest numbers as an
    OPTIMISTIC upper bound.  This caveat is also surfaced in the result dict
    under `result["caveats"]` and persisted to the saved JSON.

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

# Ensure quant/ is on sys.path before importing from constants (supports both
# `python quant/backtester.py` and `python -m quant.backtester` invocations).
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from constants import MAX_POSITIONS, MAX_PER_SECTOR, CANCEL_GAP_PCT, ATR_STOP_MULT

DEFAULT_CONFIG = {
    "INITIAL_CAPITAL":     100_000.0,
    "MAX_POSITIONS":       MAX_POSITIONS,
    "LOOKBACK_CALENDAR_DAYS": 400,   # enough for 200-day MA + features
    # Trailing stop config (set TRAIL_TRIGGER_ATR_MULT=0 to disable, use fixed target)
    "TRAIL_TRIGGER_ATR_MULT": 0,     # activate trail when profit >= N × ATR (0=off)
    "TRAIL_OFFSET_ATR_MULT":  0,     # trailing stop = high_water - N × ATR
}


def _open_positions_cash_populated():
    """Check whether data/open_positions.json has a non-null cash_usd field.

    Used by BacktestEngine.run() integrity diagnostics. Returning False surfaces
    a known phantom-field condition (CLAUDE3.md §三.2) without mutating any
    decision logic — pure reporting.
    """
    try:
        path = os.path.join(_script_dir, "..", "data", "open_positions.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("cash_usd") is not None
    except Exception:
        return False


class Position:
    """Track a single open backtested position."""

    __slots__ = ("ticker", "entry_price", "entry_open_price", "stop_price",
                 "target_price", "shares", "entry_date", "strategy", "sector",
                 "high_water", "atr", "trailing_active")

    def __init__(self, ticker, entry_price, stop_price, target_price,
                 shares, entry_date, strategy, sector="Unknown",
                 entry_open_price=None, atr=None):
        self.ticker           = ticker
        self.entry_price      = entry_price               # post-slippage fill
        self.entry_open_price = entry_open_price or entry_price
        self.stop_price       = stop_price
        self.target_price     = target_price
        self.shares           = shares
        self.entry_date       = entry_date
        self.strategy         = strategy
        self.sector           = sector
        self.high_water       = entry_price               # tracks highest price seen
        self.atr              = atr or ((entry_price - stop_price) / ATR_STOP_MULT
                                        if stop_price and entry_price > stop_price else None)
        self.trailing_active  = False


class BacktestEngine:
    """
    Walk-forward backtester using the real signal pipeline.

    Args:
        universe   (list[str]): Ticker symbols to test
        start      (str):       Start date YYYY-MM-DD
        end        (str):       End date YYYY-MM-DD
        config     (dict):      Override any key in DEFAULT_CONFIG
    """

    def __init__(self, universe, start=None, end=None, config=None,
                 replay_llm=False, data_dir=None):
        self.universe   = universe
        self.config     = {**DEFAULT_CONFIG, **(config or {})}
        self.start      = pd.Timestamp(start) if start else None
        self.end        = pd.Timestamp(end)   if end   else None
        self.replay_llm = bool(replay_llm)
        # Default data_dir = repo-root/data (one up from quant/).
        if data_dir is None:
            here = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.normpath(os.path.join(here, "..", "data"))
        self.data_dir   = data_dir

    def _download_earnings_calendar(self):
        """Per-ticker sorted list of earnings dates (past + upcoming).

        Used to derive a walk-forward `days_to_earnings` per simulated day —
        without this, the dte<=3 hard block in signal_engine never fires in
        backtest and earnings-window signals leak through (production
        rejected them; backtest accepts them, inflating survival rate).
        """
        import numpy as np
        cal = {}
        for ticker in self.universe:
            try:
                t = yf.Ticker(ticker)
                df = t.get_earnings_dates(limit=20)
                if df is None or df.empty:
                    cal[ticker] = []
                    continue
                # Index is timezone-aware datetime; normalize to date.
                dates = sorted({pd.Timestamp(d).normalize().date()
                                for d in df.index})
                cal[ticker] = dates
            except Exception as e:
                logger.debug(f"{ticker}: earnings calendar unavailable - {e}")
                cal[ticker] = []
        n_with = sum(1 for v in cal.values() if v)
        logger.info(f"Earnings calendar: {n_with}/{len(cal)} tickers populated")
        return cal

    @staticmethod
    def _earnings_dict_for(today, calendar_dates):
        """Build the earnings_data dict feature_layer expects, walked to `today`.

        Only `next_earnings_date` + `days_to_earnings` are reconstructable
        historically; eps_estimate / surprise stats are TODAY-snapshot values
        in data_layer and have no persisted history, so we leave them None.
        That's fine - signal_engine's gates only consult dte.
        """
        import numpy as np
        today_date = today.date() if hasattr(today, "date") else today
        future = [d for d in calendar_dates if d > today_date]
        if not future:
            return {
                "next_earnings_date": None, "days_to_earnings": None,
                "eps_estimate": None, "eps_actual_last": None,
                "historical_surprise_pct": [],
                "avg_historical_surprise_pct": None,
            }
        nxt = future[0]
        try:
            dte = int(np.busday_count(today_date, nxt))
        except Exception:
            dte = None
        return {
            "next_earnings_date": str(nxt), "days_to_earnings": dte,
            "eps_estimate": None, "eps_actual_last": None,
            "historical_surprise_pct": [],
            "avg_historical_surprise_pct": None,
        }

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

        earnings_calendar = self._download_earnings_calendar()

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

        # LLM replay bookkeeping (§4.2 attribution requirement).
        llm_dates_covered  = []
        llm_dates_missing  = []
        llm_signals_presented = 0
        llm_signals_vetoed    = 0
        llm_signals_passed    = 0

        # News-archive coverage bookkeeping (§6.1 parity measurement).
        # Parallel to llm_gate_unreplayed: replaces the hard-coded
        # news_veto_unreplayed=True bool with archive coverage data so a
        # future news-veto replay can be built without guessing availability.
        # Measurement-only — no decision logic reads from these lists.
        news_archive_dates_covered = []
        news_archive_dates_missing = []

        for day_idx, today in enumerate(sim_dates):

            # News-archive presence check (§6.1 measurement instrumentation).
            # Records whether data/clean_trade_news_YYYYMMDD.json exists for
            # this simulation day. Does NOT gate signals — pure observation.
            _today_str = today.strftime("%Y%m%d")
            _news_archive_path = os.path.join(
                self.data_dir, f"clean_trade_news_{_today_str}.json")
            if os.path.exists(_news_archive_path):
                news_archive_dates_covered.append(_today_str)
            else:
                news_archive_dates_missing.append(_today_str)

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

                # Trailing stop logic: update high_water, check activation,
                # dynamically raise stop if trailing is active.
                trail_trigger = self.config.get("TRAIL_TRIGGER_ATR_MULT", 0)
                trail_offset  = self.config.get("TRAIL_OFFSET_ATR_MULT", 0)
                if trail_trigger > 0 and pos.atr:
                    pos.high_water = max(pos.high_water, high)
                    profit_in_atr = (pos.high_water - pos.entry_price) / pos.atr
                    if profit_in_atr >= trail_trigger:
                        pos.trailing_active = True
                        trail_stop = round(pos.high_water - trail_offset * pos.atr, 2)
                        # Only raise the stop, never lower it
                        if trail_stop > (pos.stop_price or 0):
                            pos.stop_price = trail_stop
                        # Remove fixed target — let the trail run
                        pos.target_price = None

                # Stop hit (gap-fill or intraday) — sell slippage on top.
                if pos.stop_price and low <= pos.stop_price:
                    exit_raw_price = opn if opn < pos.stop_price else pos.stop_price
                    exit_price     = apply_stop_fill(opn, pos.stop_price)
                    exit_reason    = "trailing_stop" if pos.trailing_active else "stop"
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
                earn = self._earnings_dict_for(
                    today, earnings_calendar.get(ticker, []))
                features_dict[ticker] = compute_features(ticker, data_slice, earn)

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
            _sector_counts = {}
            _capped = []
            for s in signals:
                sec = s.get("sector", "Unknown")
                _sector_counts[sec] = _sector_counts.get(sec, 0) + 1
                if _sector_counts[sec] <= MAX_PER_SECTOR:
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

            # ── 2b. LLM gate replay (optional; off by default). ─────────────
            # When on, closes production/backtest parity for dates where
            # data/llm_prompt_resp_YYYYMMDD.json exists. See llm_replay.py.
            if self.replay_llm:
                from llm_replay import get_llm_decision_for_date, apply_llm_gate
                decision = get_llm_decision_for_date(today, self.data_dir)
                if decision["file_present"]:
                    llm_dates_covered.append(decision["date_str"])
                    signals, presented_n, vetoed_n = apply_llm_gate(signals, decision)
                    llm_signals_presented += presented_n
                    llm_signals_vetoed    += vetoed_n
                    llm_signals_passed    += len(signals)
                else:
                    llm_dates_missing.append(decision["date_str"])

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

                # Cancel if gap too large (> CANCEL_GAP_PCT above signal entry).
                # The gap check uses the RAW Open (not slippage-adjusted) so the
                # cancel boundary is determined by market conditions, not by our
                # own execution-cost assumptions.
                signal_entry = sig.get("entry_price", fill_price)
                if fill_price > signal_entry * (1 + CANCEL_GAP_PCT):
                    continue

                # Symmetric cancel: if overnight gap-down pushes the fill at or below
                # the pre-computed stop, the position is already stopped-out on day 0.
                # No valid R:R remains — skip the entry entirely.
                if stop is not None and fill_price <= stop:
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

        # LEGACY Sharpe: per-trade P&L × sqrt(30). Kept for historical
        # comparability against prior backtest_results_*.json files.
        # Known issues: dollar-denominated (not %), hand-picked sqrt(30) annualization,
        # no "flat day" dilution from equity curve. See CLAUDE3.md iteration v2.
        pnl_series = [t["pnl"] for t in closed]
        if len(pnl_series) >= 2:
            mean_pnl = sum(pnl_series) / len(pnl_series)
            var_pnl  = sum((x - mean_pnl) ** 2 for x in pnl_series) / (len(pnl_series) - 1)
            std_pnl  = math.sqrt(var_pnl) if var_pnl > 0 else 0
            sharpe_legacy = round((mean_pnl / std_pnl) * math.sqrt(30), 2) if std_pnl > 0 else None
        else:
            sharpe_legacy = None

        # DAILY Sharpe: equity-curve-based, annualized with sqrt(252).
        # Additive measurement — does NOT enter compute_convergence (that still
        # reads `sharpe`). This number is for humans to read alongside the
        # legacy value and form a trust verdict.
        equity_series = [eq for _, eq in equity_curve]
        sharpe_daily = None
        daily_returns = []
        if len(equity_series) >= 2:
            for i in range(1, len(equity_series)):
                prev = equity_series[i - 1]
                if prev > 0:
                    daily_returns.append((equity_series[i] / prev) - 1)
            if len(daily_returns) >= 2:
                mean_r = sum(daily_returns) / len(daily_returns)
                var_r  = sum((x - mean_r) ** 2 for x in daily_returns) / (len(daily_returns) - 1)
                std_r  = math.sqrt(var_r) if var_r > 0 else 0
                sharpe_daily = round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else None

        # Backwards-compatible: convergence.py + downstream readers continue to
        # use `sharpe` (legacy). `sharpe_daily` sits alongside for auditing.
        sharpe = sharpe_legacy

        survival_rate = (round(total_signals_survived / total_signals_generated, 4)
                         if total_signals_generated > 0 else 0)

        from strategy_attribution import aggregate_by_strategy
        by_strategy = aggregate_by_strategy([
            {**t, "pnl_usd": t["pnl"]} for t in closed
        ])

        # ── Benchmarks: SPY / QQQ buy-and-hold over the same window ──
        # The strategy's value is whatever it adds on top of free index exposure;
        # without this comparison a 20% return is impossible to evaluate.
        def _buy_hold(df, start_d, end_d):
            try:
                sliced = df.loc[start_d:end_d]
            except Exception:
                return None
            if sliced is None or len(sliced) < 2:
                return None
            try:
                return float(sliced["Close"].iloc[-1] / sliced["Close"].iloc[0] - 1)
            except Exception:
                return None

        spy_ret = _buy_hold(ohlcv_all.get("SPY"), sim_dates[0], sim_dates[-1])
        qqq_ret = _buy_hold(ohlcv_all.get("QQQ"), sim_dates[0], sim_dates[-1])
        strat_ret = (sum(t["pnl"] for t in closed)
                     / self.config["INITIAL_CAPITAL"])
        benchmarks = {
            "spy_buy_hold_return_pct":   round(spy_ret, 4) if spy_ret is not None else None,
            "qqq_buy_hold_return_pct":   round(qqq_ret, 4) if qqq_ret is not None else None,
            "strategy_total_return_pct": round(strat_ret, 4),
            "strategy_vs_spy_pct":       (round(strat_ret - spy_ret, 4)
                                          if spy_ret is not None else None),
            "strategy_vs_qqq_pct":       (round(strat_ret - qqq_ret, 4)
                                          if qqq_ret is not None else None),
        }

        # Equity-curve integrity — guard against "right formula, wrong inputs".
        # `sharpe_daily` is only trustworthy if the equity curve is not mostly
        # flat (which would give an artificially low std denominator).
        EQUITY_FLAT_EPS = 1e-9
        equity_flat_days = sum(1 for r in daily_returns if abs(r) < EQUITY_FLAT_EPS)
        open_positions_cash_populated = _open_positions_cash_populated()
        equity_curve_integrity = {
            "cash_field_present_in_open_positions": open_positions_cash_populated,
            "risk_rules_enforced_in_backtest":      True,  # synthetic stop_price
            "equity_curve_len":                     len(equity_series),
            "trading_days":                         len(sim_dates),
            "equity_flat_days":                     equity_flat_days,
            "equity_flat_fraction": (round(equity_flat_days / len(daily_returns), 4)
                                     if daily_returns else None),
            "daily_returns_count":                  len(daily_returns),
        }

        # Structured disclosure of known measurement biases. Does NOT enter
        # compute_convergence — pure audit surface.
        trading_days_n  = len(sim_dates)
        llm_covered_n   = len(llm_dates_covered)
        llm_missing_n   = len(llm_dates_missing)
        coverage_frac   = (round(llm_covered_n / trading_days_n, 4)
                           if trading_days_n else 0.0)

        # News-archive coverage (measurement-only, parallel to llm_gate_unreplayed).
        # No replay mechanism exists yet — archive_replay_enabled is always False.
        # When coverage_fraction rises above a useful threshold, a future
        # experiment can build a news_replay.py module on top of this bucket.
        news_archive_covered_n = len(news_archive_dates_covered)
        news_archive_missing_n = len(news_archive_dates_missing)
        news_archive_coverage_frac = (
            round(news_archive_covered_n / trading_days_n, 4)
            if trading_days_n else 0.0
        )

        known_biases = {
            # Structured audit bucket — previously a bare bool(True). Upgraded
            # on 2026-04-18 to parallel llm_gate_unreplayed's shape so downstream
            # readers can quantify the parity gap rather than just see a flag.
            "news_veto_unreplayed": {
                "archive_replay_enabled":    False,   # no replay mechanism yet
                "archive_coverage_fraction": news_archive_coverage_frac,
                "archive_dates_covered":     list(news_archive_dates_covered),
                "archive_dates_missing_n":   news_archive_missing_n,
            },
            "llm_gate_unreplayed": {
                "enabled":            self.replay_llm,
                "coverage_fraction":  coverage_frac,
                "dates_covered":      list(llm_dates_covered),
                "dates_missing_n":    llm_missing_n,
            },
            "survivorship_bias_universe":  True,
            "notes": [
                "news veto lives in filter.py (EVENT_KEYWORDS + T1_TITLE_KEYWORDS); clean_trade_news_YYYYMMDD.json archive coverage is reported but no replay engine exists yet",
                "LLM gate: production gates new_trade via llm_advisor; backtest replays only when --replay-llm is on AND llm_prompt_resp_YYYYMMDD.json exists",
                "data_layer.get_universe() reads current watchlist, not point-in-time",
            ],
        }

        # §4.2 LLM attribution bucket. replay_enabled=False → counts are zero
        # and veto_rate=None (no replay performed).
        llm_attribution = {
            "replay_enabled":       self.replay_llm,
            "coverage_fraction":    coverage_frac,
            "trading_days":         trading_days_n,
            "dates_covered":        llm_covered_n,
            "dates_missing":        llm_missing_n,
            "signals_presented":    llm_signals_presented,
            "signals_vetoed_by_llm": llm_signals_vetoed,
            "signals_passed_by_llm": llm_signals_passed,
            "veto_rate":            (round(llm_signals_vetoed / llm_signals_presented, 4)
                                     if llm_signals_presented else None),
            "notes": [
                "Counts include only days where llm_prompt_resp_YYYYMMDD.json was present.",
                "position_actions are NOT replayed — exits already run code-deterministic rule engine.",
            ],
        }

        result = {
            "period":              f"{sim_dates[0].date()} → {sim_dates[-1].date()}",
            "trading_days":        len(sim_dates),
            "total_trades":        total,
            "wins":                len(wins),
            "losses":              len(losses),
            "win_rate":            round(len(wins) / total, 4) if total else 0,
            "total_pnl":           round(sum(t["pnl"] for t in closed), 2),
            "sharpe":              sharpe,
            "sharpe_daily":        sharpe_daily,
            "sharpe_method":       "per_trade_sqrt30_legacy",
            "max_drawdown_pct":    round(max_dd, 4),
            "signals_generated":   total_signals_generated,
            "signals_survived":    total_signals_survived,
            "survival_rate":       survival_rate,
            "by_strategy":         by_strategy,
            "benchmarks":          benchmarks,
            "known_biases":        known_biases,
            "llm_attribution":     llm_attribution,
            "equity_curve_integrity": equity_curve_integrity,
            "caveats": [
                "news_veto_not_replayed: production filter.py T1-negative-news "
                "veto has no historical archive; signals rejected by news in "
                "live runs are still accepted here. Treat metrics as an "
                "OPTIMISTIC upper bound.",
            ],
            "equity_curve":        equity_curve,
            "trades":              closed,
        }

        from convergence import compute_convergence, compute_expected_value_score
        result["expected_value_score"] = compute_expected_value_score(result)
        result["convergence"] = compute_convergence(result)

        # v2 shadow verdict — what convergence WOULD say if we also required
        # sharpe_daily >= sharpe_min. Does not mutate the real verdict.
        from convergence import CRITERIA as _CRIT
        sharpe_daily_pass = (sharpe_daily is not None
                             and sharpe_daily >= _CRIT["sharpe_min"])
        result["converged_v2_shadow"] = {
            "sharpe_daily":                 sharpe_daily,
            "sharpe_daily_would_pass":      bool(sharpe_daily_pass),
            "converged_if_sharpe_daily":    bool(
                result["convergence"]["converged"] and sharpe_daily_pass),
        }
        return result

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
                replay_llm=self.replay_llm,
                data_dir=self.data_dir,
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
    print(f"  Sharpe (legacy):   {results['sharpe']}")
    print(f"  Sharpe (daily):    {results.get('sharpe_daily')}")
    print(f"  EV score:          {results.get('expected_value_score')}")
    print(f"  Max drawdown:      {results['max_drawdown_pct']*100:.2f}%")
    print(f"  Signals generated: {results['signals_generated']}")
    print(f"  Signals survived:  {results['signals_survived']}")
    print(f"  Survival rate:     {results['survival_rate']*100:.1f}%")
    print("=" * 60)

    if results.get("by_strategy"):
        from strategy_attribution import format_attribution_table
        print("\n  PER-STRATEGY ATTRIBUTION:")
        print(format_attribution_table(results["by_strategy"]))

    if results.get("benchmarks"):
        b = results["benchmarks"]
        print("\n  BENCHMARKS (buy-and-hold same window):")
        def _fmt(v):
            return f"{v*100:+.2f}%" if v is not None else "  N/A"
        print(f"    SPY return:      {_fmt(b.get('spy_buy_hold_return_pct'))}")
        print(f"    QQQ return:      {_fmt(b.get('qqq_buy_hold_return_pct'))}")
        print(f"    Strategy return: {_fmt(b.get('strategy_total_return_pct'))}")
        print(f"    vs SPY:          {_fmt(b.get('strategy_vs_spy_pct'))}")
        print(f"    vs QQQ:          {_fmt(b.get('strategy_vs_qqq_pct'))}")

    if results.get("convergence"):
        from convergence import format_convergence_report
        print("\n  CONVERGENCE:")
        print(format_convergence_report(results["convergence"]))

    shadow = results.get("converged_v2_shadow")
    if shadow:
        print("\n  V2 SHADOW (observation — does NOT change verdict above):")
        print(f"    sharpe_daily:              {shadow.get('sharpe_daily')}")
        print(f"    sharpe_daily would pass:   {shadow.get('sharpe_daily_would_pass')}")
        print(f"    converged if also gated:   {shadow.get('converged_if_sharpe_daily')}")

    llm_attr = results.get("llm_attribution")
    if llm_attr:
        print("\n  LLM ATTRIBUTION:")
        print(f"    replay_enabled:          {llm_attr.get('replay_enabled')}")
        print(f"    coverage:                "
              f"{llm_attr.get('dates_covered')}/{llm_attr.get('trading_days')} days "
              f"({(llm_attr.get('coverage_fraction') or 0)*100:.1f}%)")
        print(f"    signals presented:       {llm_attr.get('signals_presented')}")
        print(f"    vetoed by LLM:           {llm_attr.get('signals_vetoed_by_llm')}")
        print(f"    passed by LLM:           {llm_attr.get('signals_passed_by_llm')}")
        print(f"    veto_rate:               {llm_attr.get('veto_rate')}")

    integrity = results.get("equity_curve_integrity")
    if integrity:
        print("\n  EQUITY-CURVE INTEGRITY:")
        print(f"    cash_usd populated in open_positions: "
              f"{integrity.get('cash_field_present_in_open_positions')}")
        flat = integrity.get("equity_flat_fraction")
        flat_str = f"{flat*100:.1f}%" if flat is not None else "N/A"
        print(f"    flat-equity days fraction:            {flat_str}")
        print(f"    daily returns sampled:                "
              f"{integrity.get('daily_returns_count')}")

    if results.get("caveats"):
        print("\n  CAVEATS (parity gaps vs production):")
        for c in results["caveats"]:
            print(f"    - {c}")

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


def _build_stability_diagnostics(primary, secondary):
    """Structured cross-window comparison — observation only, no PASS/FAIL.

    Returns a dict with per-metric deltas and simple consistency booleans.
    Consumers (humans, future gating logic) decide how to act on it.
    """
    if not primary or not secondary or "error" in secondary:
        return None

    def _sub(a, b):
        if a is None or b is None:
            return None
        return round(a - b, 4)

    p_dd = primary.get("max_drawdown_pct")
    s_dd = secondary.get("max_drawdown_pct")
    p_ret = (primary.get("benchmarks") or {}).get("strategy_total_return_pct")
    s_ret = (secondary.get("benchmarks") or {}).get("strategy_total_return_pct")

    return {
        "stable_across_windows": {
            "expected_value_score_delta":  _sub(primary.get("expected_value_score"),
                                               secondary.get("expected_value_score")),
            "sharpe_legacy_delta":           _sub(primary.get("sharpe"),
                                                 secondary.get("sharpe")),
            "sharpe_daily_delta":            _sub(primary.get("sharpe_daily"),
                                                 secondary.get("sharpe_daily")),
            "max_drawdown_delta":            _sub(p_dd, s_dd),
            "drawdown_consistent": (p_dd is not None and s_dd is not None
                                    and abs(p_dd - s_dd) <= 0.05),
            "directionally_profitable_both": (p_ret is not None and s_ret is not None
                                              and p_ret > 0 and s_ret > 0),
            "primary_expected_value_score":  primary.get("expected_value_score"),
            "secondary_expected_value_score": secondary.get("expected_value_score"),
            "primary_sharpe_daily":          primary.get("sharpe_daily"),
            "secondary_sharpe_daily":        secondary.get("sharpe_daily"),
            "primary_return_pct":            p_ret,
            "secondary_return_pct":          s_ret,
        }
    }


def _print_diagnostics(diagnostics):
    """Pretty-print the stability diagnostics block."""
    if not diagnostics:
        return
    s = diagnostics.get("stable_across_windows") or {}
    print("\n" + "=" * 60)
    print("  CROSS-WINDOW STABILITY (observation only)")
    print("=" * 60)

    def _fmt(v):
        if v is None:
            return "N/A"
        return f"{v:+.4f}" if isinstance(v, float) else str(v)

    print(f"  primary EV score:        {_fmt(s.get('primary_expected_value_score'))}")
    print(f"  secondary EV score:      {_fmt(s.get('secondary_expected_value_score'))}")
    print(f"  Δ EV score:              {_fmt(s.get('expected_value_score_delta'))}")
    print(f"  primary sharpe_daily:    {_fmt(s.get('primary_sharpe_daily'))}")
    print(f"  secondary sharpe_daily:  {_fmt(s.get('secondary_sharpe_daily'))}")
    print(f"  Δ sharpe_legacy:         {_fmt(s.get('sharpe_legacy_delta'))}")
    print(f"  Δ sharpe_daily:          {_fmt(s.get('sharpe_daily_delta'))}")
    print(f"  Δ max_drawdown:          {_fmt(s.get('max_drawdown_delta'))}")
    print(f"  drawdown_consistent:     {s.get('drawdown_consistent')}")
    print(f"  profitable in both:      {s.get('directionally_profitable_both')}")
    print("=" * 60)


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
    parser.add_argument("--no-secondary", action="store_true",
                        help="Skip the non-overlapping secondary-window diagnostic run")
    parser.add_argument("--replay-llm", action="store_true",
                        help="Apply LLM gate using data/llm_prompt_resp_YYYYMMDD.json "
                             "when the file exists (§6.1 parity fix). Default: off.")
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

    engine = BacktestEngine(universe, start=args.start, end=args.end,
                            replay_llm=args.replay_llm)

    if args.sweep and len(args.sweep) >= 2:
        param_name = args.sweep[0]
        raw = [float(v) for v in args.sweep[1:]]
        values = [int(v) if v == int(v) else v for v in raw]
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

        # Diagnostic: non-overlapping secondary window immediately preceding
        # the primary. Report-only — does NOT change convergence verdict.
        secondary = None
        diagnostics = None
        if not args.no_secondary:
            try:
                primary_start = pd.Timestamp(args.start)
                secondary_end = (primary_start - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                secondary_start = (primary_start - pd.Timedelta(days=183)).strftime("%Y-%m-%d")
                print(f"\n--- SECONDARY WINDOW DIAGNOSTIC: "
                      f"{secondary_start} → {secondary_end} ---")
                secondary_engine = BacktestEngine(
                    universe, start=secondary_start, end=secondary_end,
                    replay_llm=args.replay_llm)
                secondary = secondary_engine.run()
                if "error" in secondary:
                    print(f"  (secondary run failed: {secondary['error']})")
                    secondary = {"error": secondary["error"]}
                else:
                    _print_results(secondary)
                    diagnostics = _build_stability_diagnostics(results, secondary)
                    _print_diagnostics(diagnostics)
            except Exception as e:
                print(f"  (secondary run exception: {e})")
                secondary = {"error": str(e)}

        # Save results. Combined layout when secondary is present; flat when not
        # (preserves the historical shape consumed by downstream readers).
        out_path = os.path.join(script_dir, "..", "data",
                                f"backtest_results_{datetime.now().strftime('%Y%m%d')}.json")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

        primary_save = {k: v for k, v in results.items() if k != "equity_curve"}
        if secondary is not None:
            secondary_save = ({k: v for k, v in secondary.items() if k != "equity_curve"}
                              if "error" not in secondary else secondary)
            save_data = {
                **primary_save,                 # flat keys preserved for compat
                "primary":     primary_save,
                "secondary":   secondary_save,
                "diagnostics": diagnostics,
            }
        else:
            save_data = primary_save

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        print(f"Results saved → {out_path}")


if __name__ == "__main__":
    main()
