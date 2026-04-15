#!/usr/bin/env python3
"""
Forward test validator for LLM trading recommendations.

For each llm_output_YYYYMMDD.json, evaluates recommendation quality by checking
actual price performance N trading days after the recommendation date.

Logic:
  - EXIT / REDUCE → correct if price fell (protected capital)
  - HOLD          → correct if price rose or stayed flat
  - NEW TRADE     → correct if price rose (long trade)

Usage:
    # Evaluate all llm_output files that are old enough
    python forward_tester.py

    # Specific file
    python forward_tester.py --file data/llm_output_20260219.json

    # Change evaluation window (default 10 trading days)
    python forward_tester.py --days 5
"""

import os
import math
import json
import glob
import logging
import argparse
from datetime import datetime, date, timedelta

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

EVAL_DAYS    = 10          # Default trading-day window
EVAL_WINDOWS = [10, 20, 30]  # Multi-window evaluation (primary + extended)
DATA_DIR     = "data"


# ---------------------------------------------------------------------------
# Fill model — shared with backtester.py via quant/fill_model.py
# ---------------------------------------------------------------------------
# Re-export SLIPPAGE_BPS_* and apply_slippage under this module's namespace so
# existing `from forward_tester import apply_slippage, SLIPPAGE_BPS_STOP`
# imports in test_quant.py keep working without edits.
from fill_model import (
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_STOP,
    SLIPPAGE_BPS_TARGET,
    apply_slippage,
)

# Round-trip commission + spread cost as a fraction of notional, applied once
# to a completed trade's realized P&L.  Separate from the per-fill slippage
# above: slippage models the price you actually get on each leg, commission
# models the per-trade friction (broker fees, regulatory, spread residual).
#
# Single source of truth lives in portfolio_engine.ROUND_TRIP_COST_PCT so the
# two simulators cannot drift from the live sizing logic.  Imported under the
# legacy `ROUND_TRIP_COST` name because test_quant.py already imports it that
# way.
from portfolio_engine import ROUND_TRIP_COST_PCT as ROUND_TRIP_COST


def get_next_open_price(ticker, rec_date):
    """Fetch the Open of the first trading day STRICTLY AFTER rec_date.

    Models realistic execution: signals are produced end-of-day, so the
    earliest fill is the next session's opening auction.  Before this helper
    existed, entry was assumed at rec_date close, which overstates edge
    because (a) signals often can't be acted on before close and (b) the
    opening auction is usually a worse fill than the prior close.
    """
    try:
        start = pd.Timestamp(rec_date) + pd.Timedelta(days=1)
        end   = pd.Timestamp(rec_date) + pd.Timedelta(days=7)
        data  = yf.download(ticker, start=start, end=end, progress=False)
        if data.empty:
            return None, None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if "Open" not in data.columns:
            return None, None
        first = data.index[0]
        raw   = data.loc[first, "Open"]
        price = float(raw.item() if hasattr(raw, "item") else raw)
        return round(price, 4), first.date()
    except Exception as e:
        logger.warning(f"Failed to fetch next-open for {ticker} after {rec_date}: {e}")
        return None, None


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

def get_close_price(ticker, target_date):
    """
    Fetch closing price on or immediately after target_date.

    Returns:
        (price: float, actual_date: date) or (None, None) if unavailable
    """
    try:
        start = pd.Timestamp(target_date) - pd.Timedelta(days=3)
        end   = pd.Timestamp(target_date) + pd.Timedelta(days=7)

        data = yf.download(ticker, start=start, end=end, progress=False)
        if data.empty:
            return None, None

        target_ts  = pd.Timestamp(target_date)
        candidates = data.index[data.index >= target_ts]
        if len(candidates) == 0:
            return None, None

        row        = data.loc[candidates[0], "Close"]
        price      = float(row.item() if hasattr(row, "item") else row)
        actual_dt  = candidates[0].date()
        return round(price, 4), actual_dt

    except Exception as e:
        logger.warning(f"Failed to fetch price for {ticker} on {target_date}: {e}")
        return None, None


def get_daily_prices_during_period(ticker, start_date, end_date):
    """
    Fetch daily OHLC prices between start_date and end_date (inclusive).

    Used to detect whether a stop-loss was hit during the evaluation window,
    which pure endpoint comparison misses entirely.  Open is required to
    detect gap-through-stop fills: when a stock gaps below the stop at open,
    execution occurs at the opening price, not at the stop price.

    Returns:
        pd.DataFrame with columns [Open, High, Low, Close] indexed by date, or None
    """
    try:
        data = yf.download(
            ticker,
            start=pd.Timestamp(start_date),
            end=pd.Timestamp(end_date) + pd.Timedelta(days=2),
            progress=False,
        )
        if data.empty:
            return None
        # Flatten MultiIndex if present (yfinance quirk)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        required = ["Open", "High", "Low", "Close"]
        if not all(c in data.columns for c in required):
            return None
        return data[required]
    except Exception as e:
        logger.warning(f"Failed to fetch daily prices for {ticker}: {e}")
        return None


def check_stop_or_target_hit(ticker, entry_date, entry_price, stop_price, target_price, n_days):
    """
    Scan daily prices during the evaluation window to determine if the stop or
    target was hit before the end of the period.

    The 10-day endpoint comparison in action_is_correct() is misleading when:
    - A trade hit the stop on day 3 then recovered above entry by day 10
      (shows "correct" but was actually a loss)
    - A trade hit the target on day 5 then gave back gains by day 10
      (shows "incorrect" but was actually a win)

    Args:
        ticker       (str):   Ticker symbol
        entry_date   (date):  Date of recommendation (day 0)
        entry_price  (float): Planned entry price
        stop_price   (float): Stop-loss price
        target_price (float): Profit-target price (or None if unknown)
        n_days       (int):   Trading-day evaluation window

    Returns:
        dict: {
            "stop_hit":         bool,
            "stop_hit_day":     int or None,      # trading day index (1-based)
            "stop_hit_price":   float or None,    # SLIPPAGE-ADJUSTED stop fill price
            "target_hit":       bool,
            "target_hit_day":   int or None,
            "target_hit_price": float or None,    # SLIPPAGE-ADJUSTED target fill price
            "exit_reason":      "stop" | "target" | None,  # first-touch reason
            "data_available":   bool,
        }

    Fills are slippage-adjusted (SLIPPAGE_BPS_STOP / SLIPPAGE_BPS_TARGET) so
    the returned price is what the trade would actually realize, not the
    theoretical trigger level.  Gap-through handling is preserved: if Open
    has already crossed the level, fill uses Open; otherwise the trigger
    level is used as the raw fill and slippage is applied on top.
    """
    result = {
        "stop_hit":         False,
        "stop_hit_day":     None,
        "stop_hit_price":   None,
        "target_hit":       False,
        "target_hit_day":   None,
        "target_hit_price": None,
        "exit_reason":      None,
        "data_available":   False,
    }

    # Fetch slightly beyond the window to cover weekends / holidays
    window_end  = get_eval_date(entry_date, n_days)
    daily       = get_daily_prices_during_period(ticker, entry_date, window_end)
    if daily is None or daily.empty:
        return result

    result["data_available"] = True
    # Only inspect trading days AFTER the recommendation date (day 1 onward)
    future_days = daily[daily.index.date > entry_date]

    for day_idx, (ts, row) in enumerate(future_days.iterrows(), start=1):
        open_p = float(row["Open"].item()  if hasattr(row["Open"],  "item") else row["Open"])
        low    = float(row["Low"].item()   if hasattr(row["Low"],   "item") else row["Low"])
        high   = float(row["High"].item()  if hasattr(row["High"],  "item") else row["High"])

        # Stop hit: daily Low touches or breaches stop_price
        if not result["stop_hit"] and stop_price and low <= stop_price:
            result["stop_hit"]     = True
            result["stop_hit_day"] = day_idx
            # Fill price depends on whether the stop was hit via a gap or intraday:
            #   Gap-down (open < stop): market opens below stop → execution at open price.
            #   Intraday stop (open >= stop): price drifts to stop during the session
            #     → execution approximated at stop_price (limit/stop-limit order).
            # Using low (the day's minimum) as fill would overstate the loss in both cases.
            raw_stop_fill = open_p if open_p < stop_price else stop_price
            result["stop_hit_price"] = apply_slippage(
                raw_stop_fill, SLIPPAGE_BPS_STOP, "sell")
            if result["exit_reason"] is None:
                result["exit_reason"] = "stop"

        # Target hit: daily High reaches or exceeds target_price
        if not result["target_hit"] and target_price and high >= target_price:
            result["target_hit"]     = True
            result["target_hit_day"] = day_idx
            # Gap-up (open >= target): market opens above target → fill at open (bonus).
            # Intraday (open < target, high >= target): fill at target (limit order).
            raw_target_fill = open_p if open_p >= target_price else target_price
            result["target_hit_price"] = apply_slippage(
                raw_target_fill, SLIPPAGE_BPS_TARGET, "sell")
            # Only set exit_reason if stop didn't already claim it earlier in the loop.
            # Same-day stop+target → stop wins (conservative; see tie-break below).
            if result["exit_reason"] is None:
                result["exit_reason"] = "target"

        # Stop found first — subsequent target hit is irrelevant for this trade
        if result["stop_hit"] and result["target_hit"]:
            break

    return result


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def get_eval_date(rec_date, n_trading_days=EVAL_DAYS):
    """Return the date n business days after rec_date (approximate — ignores US holidays)."""
    dates = pd.bdate_range(start=rec_date + timedelta(days=1), periods=n_trading_days)
    return dates[-1].date()


def parse_date_from_filename(filepath):
    """Extract YYYYMMDD date from investment_advice_YYYYMMDD.json filename.

    Also supports legacy llm_output_YYYYMMDD.json format.
    Assumes the date is always the last underscore-delimited token before the extension.
    """
    basename = os.path.basename(filepath)
    stem = os.path.splitext(basename)[0]   # investment_advice_YYYYMMDD
    date_str = stem.split("_")[-1]         # YYYYMMDD
    return datetime.strptime(date_str, "%Y%m%d").date()


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

PROFIT_LOCKING_RULES = frozenset({
    "PROFIT_TARGET", "SIGNAL_TARGET", "PROFIT_LADDER_50", "PROFIT_LADDER_30",
})

# Timing tolerance: a profit-lock REDUCE is "timing_correct" when the sell price
# is within this percent of the subsequent window's peak.  5% is the default
# because the standard 3.5×ATR profit target sits roughly 3.5% above the 1.5×ATR
# stop; leaving less than 5% on the table is within the natural noise band of
# the trade structure.  Adjust only with evidence from forward_tester output.
TIMING_TOLERANCE_PCT = 0.05


def action_is_correct(action, return_10d, exit_rule=None):
    """
    Determine if the recommendation was DIRECTIONALLY correct.

    This is a pure direction check — it does NOT evaluate timing quality.
    For profit-locking REDUCEs (PROFIT_TARGET, SIGNAL_TARGET, PROFIT_LADDER_*),
    the rule fired as designed so direction is always "correct"; but timing
    quality (whether the exit left significant gain on the table) is a
    separate metric computed by ``evaluate_profit_lock_timing()`` and
    surfaced as ``timing_correct`` in ``evaluate_file()``.

    - EXIT:          correct if price went DOWN  (protected capital)
    - REDUCE (risk): correct if price went DOWN  (cut a losing/risky position)
    - REDUCE (profit-lock): always direction_correct — the rule executed at its
      planned level.  Timing quality is graded separately.
    - HOLD:          correct if price went UP or flat
    - NEW TRADE:     correct if price went UP     (long trade wins)
    """
    if action == "REDUCE" and exit_rule in PROFIT_LOCKING_RULES:
        # Rule fired at planned target → direction correct by construction.
        # Timing quality (early-exit cost) is graded by evaluate_profit_lock_timing.
        return True
    if action in ("EXIT", "REDUCE"):
        return return_10d < 0
    elif action == "HOLD":
        return return_10d >= 0
    return None     # unknown action type


def evaluate_profit_lock_timing(ticker, rec_date, eval_date, sell_price,
                                 avg_cost=None, tolerance_pct=TIMING_TOLERANCE_PCT,
                                 _daily_override=None):
    """
    Grade timing quality of a profit-locking REDUCE.

    A direction-correct profit lock can still be a mistake when the underlying
    continues to run far past the exit price — the "cut your winners short"
    failure mode of trend-following systems.  This helper quantifies how much
    gain was left on the table by comparing the sell price to the highest High
    in the evaluation window.

    Metrics emitted:
        foregone_gain_pct  = (max_high - sell_price) / sell_price
            How much additional % move was left on the table, relative to the
            sell price.  This is the headline "early-exit cost" metric.
        peak_capture_pct   = (sell_price - avg_cost) / (max_high - avg_cost)
            Of the hypothetical cost-to-peak move, what fraction was captured?
            Requires avg_cost; falls back to (1 - foregone_gain_pct) capped to
            [0,1] when avg_cost is unavailable.
        timing_correct     = foregone_gain_pct < tolerance_pct
            Boolean: was the sell near the window's peak?  Default tolerance 5%.

    Args:
        ticker        (str):        Ticker symbol
        rec_date      (date):       Date the REDUCE recommendation was made
        eval_date     (date):       End of evaluation window
        sell_price    (float):      Price the profit lock executed at
                                    (typically the rec_date close)
        avg_cost      (float|None): Position's average cost, used for the
                                    cost-to-peak peak_capture formulation
        tolerance_pct (float):      foregone_gain_pct threshold for timing_correct
        _daily_override (DataFrame|None): Injected prices for unit tests.  When
                                    provided, skip the yfinance fetch and use
                                    this DataFrame directly (must have a High
                                    column and a DatetimeIndex).

    Returns:
        dict with keys:
            data_available      (bool)
            max_price_in_window (float|None)
            peak_capture_pct    (float|None)
            foregone_gain_pct   (float|None)
            timing_correct      (bool|None)
    """
    result = {
        "data_available":      False,
        "max_price_in_window": None,
        "peak_capture_pct":    None,
        "foregone_gain_pct":   None,
        "timing_correct":      None,
    }
    if sell_price is None or sell_price <= 0:
        return result

    if _daily_override is not None:
        daily = _daily_override
    else:
        daily = get_daily_prices_during_period(ticker, rec_date, eval_date)
    if daily is None or daily.empty:
        return result

    # Only inspect trading days AFTER the recommendation date (day 1 onward).
    future = daily[daily.index.date > rec_date]
    if future.empty:
        return result

    highs = future["High"]
    max_high_raw = highs.max()
    max_high = float(max_high_raw.item() if hasattr(max_high_raw, "item") else max_high_raw)

    result["data_available"]      = True
    result["max_price_in_window"] = round(max_high, 4)

    if max_high <= sell_price:
        # Stock never ran higher after the sell — timing was perfect.
        result["peak_capture_pct"]  = 1.0
        result["foregone_gain_pct"] = 0.0
        result["timing_correct"]    = True
        return result

    foregone = (max_high - sell_price) / sell_price
    result["foregone_gain_pct"] = round(foregone, 4)
    result["timing_correct"]    = foregone < tolerance_pct

    # Peak capture: cost-to-peak formulation when avg_cost is available.
    # Example: avg_cost=$100, sell=$120, peak=$140 → captured (120-100)/(140-100) = 50%.
    # When avg_cost is unavailable, fall back to 1 - foregone (a weaker but still
    # directional indicator — goes to 0 as foregone gets large).
    if avg_cost is not None and avg_cost > 0 and max_high > avg_cost:
        peak_capture = (sell_price - avg_cost) / (max_high - avg_cost)
        peak_capture = max(0.0, min(peak_capture, 1.0))
    else:
        peak_capture = max(0.0, 1.0 - foregone)
    result["peak_capture_pct"] = round(peak_capture, 4)

    return result


def evaluate_file(filepath, open_positions_path="../data/open_positions.json",
                  n_days=EVAL_DAYS):
    """
    Run forward test evaluation for a single llm_output file.

    Returns:
        dict with full evaluation results, or None if evaluation date is in the future
    """
    # Parse recommendation date
    try:
        rec_date = parse_date_from_filename(filepath)
    except Exception as e:
        logger.error(f"Cannot parse date from {filepath}: {e}")
        return None

    eval_date = get_eval_date(rec_date, n_days)

    # Check if enough time has passed
    if eval_date > date.today():
        logger.info(
            f"Skipping {os.path.basename(filepath)}: "
            f"eval date {eval_date} is in the future ({n_days}d window not yet complete)"
        )
        return None

    # Load LLM output
    # save_advice() wraps the parsed JSON: {"advice_parsed": {...}, "advice_raw": ...}
    # Support both the wrapped format and raw format for backwards-compatibility.
    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    llm_data = raw_data.get("advice_parsed") or raw_data

    # Load avg_cost from open_positions for reference
    avg_costs = {}
    pos_file = open_positions_path
    if not os.path.exists(pos_file):
        pos_file = "data/open_positions.json"
    if os.path.exists(pos_file):
        with open(pos_file, "r", encoding="utf-8") as f:
            pos_data = json.load(f)
        avg_costs = {p["ticker"]: p.get("avg_cost") for p in pos_data.get("positions", [])}

    results = {
        "file":              os.path.basename(filepath),
        "rec_date":          str(rec_date),
        "eval_date":         str(eval_date),
        "n_trading_days":    n_days,
        "position_results":  [],
        "new_trade_result":  None,
        "summary":           {},
    }

    # ------------------------------------------------------------------
    # Evaluate position_actions
    # ------------------------------------------------------------------
    for action_item in llm_data.get("position_actions", []):
        ticker     = action_item["ticker"]
        action     = action_item["action"]
        confidence = action_item.get("confidence")
        rule       = action_item.get("exit_rule_triggered", "NONE")

        price_rec,  date_rec  = get_close_price(ticker, rec_date)
        price_eval, date_eval = get_close_price(ticker, eval_date)

        if price_rec is None or price_eval is None:
            results["position_results"].append({
                "ticker":     ticker,
                "action":     action,
                "error":      "price data unavailable",
            })
            continue

        return_10d  = (price_eval - price_rec) / price_rec
        correct     = action_is_correct(action, return_10d, exit_rule=rule)
        avg_cost    = avg_costs.get(ticker)
        pnl_vs_cost = ((price_rec - avg_cost) / avg_cost) if avg_cost else None

        # Realized exit P&L for EXIT/REDUCE actions, grounded in an actual fill
        # price rather than rec_date close.  Sell is modelled as next-day Open
        # with stop-side slippage (conservative: exit decisions most often
        # correlate with adverse price moves, so stop-side is the right budget),
        # minus round-trip commission.  return_10d_pct remains the direction-
        # correctness signal; realized_exit_pnl_pct_net is for P&L attribution.
        exit_fill_price          = None
        realized_exit_pnl_pct    = None
        realized_exit_pnl_pct_net = None
        if action in ("EXIT", "REDUCE"):
            raw_exit_open, _ = get_next_open_price(ticker, rec_date)
            if raw_exit_open is not None:
                exit_fill_price = apply_slippage(
                    raw_exit_open, SLIPPAGE_BPS_STOP, "sell")
                if avg_cost:
                    realized_exit_pnl_pct = (
                        exit_fill_price / avg_cost - 1)
                    realized_exit_pnl_pct_net = (
                        realized_exit_pnl_pct - ROUND_TRIP_COST)

        position_entry = {
            "ticker":            ticker,
            "action":            action,
            "exit_rule":         rule,
            "confidence":        confidence,
            "avg_cost":          avg_cost,
            "price_on_rec_date": price_rec,
            "pnl_vs_cost_pct":   round(pnl_vs_cost, 4) if pnl_vs_cost is not None else None,
            "price_on_eval_date":price_eval,
            "return_10d_pct":    round(return_10d, 4),
            "exit_fill_price":   round(exit_fill_price, 4) if exit_fill_price is not None else None,
            "realized_exit_pnl_pct":     round(realized_exit_pnl_pct, 4)     if realized_exit_pnl_pct     is not None else None,
            "realized_exit_pnl_pct_net": round(realized_exit_pnl_pct_net, 4) if realized_exit_pnl_pct_net is not None else None,
            "action_correct":    correct,   # direction_correct (legacy name preserved)
            "actual_rec_date":   str(date_rec),
            "actual_eval_date":  str(date_eval),
        }

        # For profit-locking REDUCEs, also grade TIMING: did the sell fire
        # near the window's peak, or did the stock run significantly higher?
        # This surfaces the "cut winners short" failure mode that the old
        # "action_correct = True" for all profit locks concealed.
        if action == "REDUCE" and rule in PROFIT_LOCKING_RULES:
            timing = evaluate_profit_lock_timing(
                ticker     = ticker,
                rec_date   = rec_date,
                eval_date  = eval_date,
                sell_price = price_rec,
                avg_cost   = avg_cost,
            )
            position_entry["timing_correct"]      = timing["timing_correct"]
            position_entry["peak_capture_pct"]    = timing["peak_capture_pct"]
            position_entry["foregone_gain_pct"]   = timing["foregone_gain_pct"]
            position_entry["max_price_in_window"] = timing["max_price_in_window"]

        results["position_results"].append(position_entry)

    # ------------------------------------------------------------------
    # Evaluate new_trade (if any)
    # ------------------------------------------------------------------
    new_trade = llm_data.get("new_trade")
    if isinstance(new_trade, dict):
        ticker     = new_trade["ticker"]
        direction  = new_trade.get("direction", "long")
        confidence = new_trade.get("confidence")
        strategy   = new_trade.get("strategy")

        price_rec,  date_rec  = get_close_price(ticker, rec_date)
        price_eval, date_eval = get_close_price(ticker, eval_date)

        # Entry fill model: next-day Open + buy-side slippage.  A caller-supplied
        # entry_price (e.g. a backtest injecting a synthetic fill) still wins so
        # historical test fixtures keep working; otherwise we model realistic
        # execution: signals run EOD, order reaches the book at next open.
        entry_override = new_trade.get("entry_price")
        if entry_override is not None:
            entry_fill_price = round(float(entry_override), 4)
            entry_open_price = entry_fill_price
        else:
            entry_open_price, _ = get_next_open_price(ticker, rec_date)
            entry_fill_price = apply_slippage(
                entry_open_price, SLIPPAGE_BPS_ENTRY, "buy") if entry_open_price else None

        if price_rec is not None and price_eval is not None and entry_fill_price is not None:
            return_10d      = (price_eval - price_rec) / price_rec
            # Legacy net_return_10d_pct retained for dashboard continuity; uses
            # the close-to-close return minus a flat round-trip cost.  The
            # authoritative metric is realized_pnl_pct_net below, which is
            # grounded in the actual simulated fill prices.
            net_return_10d  = return_10d - ROUND_TRIP_COST
            correct         = action_is_correct("NEW TRADE", net_return_10d)

            # Path analysis: check if stop or target was hit DURING the evaluation window.
            # A trade that stops out on day 3 but recovers by day 10 shows as "correct"
            # using endpoint-only comparison — this is a false positive.
            stop_target_check = check_stop_or_target_hit(
                ticker       = ticker,
                entry_date   = rec_date,
                entry_price  = entry_fill_price,
                stop_price   = new_trade.get("stop_price"),
                target_price = new_trade.get("target_price"),
                n_days       = n_days,
            )

            # Exit fill: whichever of stop / target fired first, else mark-to-market
            # at eval_date close with sell-side slippage (open-ended trade).
            exit_reason      = stop_target_check.get("exit_reason")
            if exit_reason == "stop":
                exit_fill_price = stop_target_check.get("stop_hit_price")
            elif exit_reason == "target":
                exit_fill_price = stop_target_check.get("target_hit_price")
            else:
                # No trigger → exit assumed at eval_date close with exit-side slippage.
                # Use the target slippage budget (same tight liquidity assumption)
                # since no adverse-momentum surge is implied.
                exit_fill_price = apply_slippage(
                    price_eval, SLIPPAGE_BPS_TARGET, "sell")

            realized_pnl_pct = (exit_fill_price / entry_fill_price - 1)
            realized_pnl_pct_net = realized_pnl_pct - ROUND_TRIP_COST

            # Path-corrected direction: loss if stop fired first (or solo).
            path_correct = correct
            if stop_target_check.get("data_available"):
                stop_day   = stop_target_check.get("stop_hit_day")
                target_day = stop_target_check.get("target_hit_day")
                if stop_target_check["stop_hit"] and (
                    not stop_target_check["target_hit"]
                    or (stop_day is not None and target_day is not None and stop_day < target_day)
                ):
                    path_correct = False

            # Multi-window evaluation: compute returns at 20d and 30d windows
            # when enough calendar time has passed.  Trend-following strategies
            # expect 15-45 day holds; 10-day-only evaluation undervalues them.
            multi_window = {}
            for window in EVAL_WINDOWS:
                if window == n_days:
                    continue  # primary window already computed above
                _w_eval_date = get_eval_date(rec_date, window)
                if _w_eval_date > date.today():
                    continue  # not enough time has passed
                _w_price, _w_date = get_close_price(ticker, _w_eval_date)
                if _w_price is not None and price_rec:
                    _w_ret = (_w_price - price_rec) / price_rec
                    multi_window[f"return_{window}d_pct"] = round(_w_ret, 4)
                    # Extended path analysis for longer windows
                    _w_check = check_stop_or_target_hit(
                        ticker=ticker, entry_date=rec_date,
                        entry_price=new_trade.get("entry_price") or price_rec,
                        stop_price=new_trade.get("stop_price"),
                        target_price=new_trade.get("target_price"),
                        n_days=window,
                    )
                    if _w_check.get("target_hit") and not _w_check.get("stop_hit"):
                        multi_window[f"target_hit_{window}d"] = True
                        multi_window[f"target_hit_{window}d_day"] = _w_check.get("target_hit_day")

            stop_price_val = new_trade.get("stop_price")
            if stop_price_val is not None and entry_fill_price:
                initial_risk_pct = round(
                    (entry_fill_price - float(stop_price_val)) / entry_fill_price, 4)
            else:
                initial_risk_pct = None

            results["new_trade_result"] = {
                "ticker":              ticker,
                "direction":           direction,
                "confidence":          confidence,
                "strategy":            strategy,
                "initial_risk_pct":    initial_risk_pct,
                "thesis":              new_trade.get("thesis"),
                "price_on_rec_date":   price_rec,          # close of rec_date (reference)
                "price_on_eval_date":  price_eval,
                "entry_open_price":    entry_open_price,   # raw next-day Open
                "entry_fill_price":    entry_fill_price,   # next-day Open + buy slippage
                "exit_fill_price":     round(exit_fill_price, 4) if exit_fill_price else None,
                "exit_reason":         exit_reason or "eval_close",
                "return_10d_pct":      round(return_10d, 4),
                "net_return_10d_pct":  round(net_return_10d, 4),       # legacy close-based
                "realized_pnl_pct":        round(realized_pnl_pct, 4),       # fills only
                "realized_pnl_pct_net":    round(realized_pnl_pct_net, 4),   # fills + commission
                "trade_correct":       correct,        # endpoint-only (original metric)
                "path_correct":        path_correct,   # accounts for stop/target path
                "stop_hit_during_period":   stop_target_check.get("stop_hit", False),
                "stop_hit_day":             stop_target_check.get("stop_hit_day"),
                "stop_hit_price":           stop_target_check.get("stop_hit_price"),
                "target_hit_during_period": stop_target_check.get("target_hit", False),
                "target_hit_day":           stop_target_check.get("target_hit_day"),
                "target_hit_price":         stop_target_check.get("target_hit_price"),
                "actual_rec_date":     str(date_rec),
                "actual_eval_date":    str(date_eval),
                **multi_window,  # return_20d_pct, return_30d_pct when available
            }
        else:
            results["new_trade_result"] = {"ticker": ticker, "error": "price data unavailable"}

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------
    valid = [r for r in results["position_results"] if "action_correct" in r]
    if valid:
        correct_count  = sum(1 for r in valid if r["action_correct"])
        accuracy       = correct_count / len(valid)
        avg_return_all = sum(r["return_10d_pct"] for r in valid) / len(valid)

        hold_returns  = [r["return_10d_pct"] for r in valid if r["action"] == "HOLD"]
        exit_returns  = [r["return_10d_pct"] for r in valid if r["action"] in ("EXIT", "REDUCE")]

        # Profit-lock timing rollup: scans REDUCEs that carried a timing_correct
        # field (set only when exit_rule ∈ PROFIT_LOCKING_RULES).  Surfaces the
        # "cut your winners short" cost that the legacy action_correct metric
        # concealed by auto-marking profit locks as always right.
        profit_lock_entries = [
            r for r in valid
            if r.get("timing_correct") is not None
        ]
        timing_correct_count  = sum(1 for r in profit_lock_entries if r["timing_correct"])
        timing_accuracy_pct   = (round(timing_correct_count / len(profit_lock_entries) * 100, 1)
                                 if profit_lock_entries else None)
        foregone_values = sorted(
            r["foregone_gain_pct"]
            for r in profit_lock_entries
            if r.get("foregone_gain_pct") is not None
        )
        if foregone_values:
            mid = len(foregone_values) // 2
            median_foregone = (foregone_values[mid]
                               if len(foregone_values) % 2 == 1
                               else (foregone_values[mid - 1] + foregone_values[mid]) / 2)
            median_foregone_pct = round(median_foregone * 100, 2)
        else:
            median_foregone_pct = None

        results["summary"] = {
            "total_evaluated":          len(valid),
            "correct_calls":            correct_count,
            "accuracy_pct":             round(accuracy * 100, 1),
            "avg_10d_return_all_pct":   round(avg_return_all * 100, 2),
            "hold_count":               len(hold_returns),
            "avg_hold_return_pct":      round(sum(hold_returns) / len(hold_returns) * 100, 2) if hold_returns else None,
            "exit_reduce_count":        len(exit_returns),
            "avg_exit_return_pct":      round(sum(exit_returns) / len(exit_returns) * 100, 2) if exit_returns else None,
            "premature_exits":          sum(1 for r in valid
                                           if r["action"] in ("EXIT", "REDUCE")
                                           and r["return_10d_pct"] > 0),
            # Direction vs. timing are now tracked separately.  direction_accuracy_pct
            # is an alias for accuracy_pct so downstream tooling can migrate without
            # breaking legacy consumers.
            "direction_accuracy_pct":   round(accuracy * 100, 1),
            "profit_lock_count":        len(profit_lock_entries),
            "timing_correct_count":     timing_correct_count,
            "timing_accuracy_pct":      timing_accuracy_pct,
            "median_foregone_gain_pct": median_foregone_pct,
        }

    return results


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------

ACTION_ICON = {"HOLD": "◆", "REDUCE": "▼", "EXIT": "✕"}
CORRECT_ICON = {True: "✓", False: "✗", None: "?"}


def print_report(results):
    """Print human-readable forward test report to console."""
    print()
    print("=" * 72)
    print(f"  FORWARD TEST: {results['file']}")
    print("=" * 72)
    print(f"  Rec date:   {results['rec_date']}")
    print(f"  Eval date:  {results['eval_date']}  ({results['n_trading_days']} trading days later)")
    print()

    # Position actions table
    print(f"  {'Ticker':<6} {'Action':<8} {'Avg Cost':>9} {'Rec Price':>9} "
          f"{'PnL@Rec':>8} {'Eval Price':>10} {'10d Ret':>8} {'OK?':>5}")
    print("  " + "-" * 68)

    for r in results["position_results"]:
        if "error" in r:
            print(f"  {r['ticker']:<6} {r['action']:<8}  {'N/A':>9}  {'N/A':>9}  "
                  f"{'N/A':>8}  {'N/A':>10}  {'N/A':>8}  {'?':>5}")
            continue

        avg_cost   = f"${r['avg_cost']:.2f}"   if r['avg_cost']   else "  N/A"
        pnl_str    = f"{r['pnl_vs_cost_pct']*100:+.1f}%" if r['pnl_vs_cost_pct'] is not None else "  N/A"
        ret_str    = f"{r['return_10d_pct']*100:+.2f}%"
        icon       = ACTION_ICON.get(r["action"], " ")
        correct    = CORRECT_ICON.get(r["action_correct"], "?")

        print(f"  {r['ticker']:<6} {icon} {r['action']:<6} {avg_cost:>9} "
              f"${r['price_on_rec_date']:>8.2f} {pnl_str:>8} "
              f"${r['price_on_eval_date']:>9.2f} {ret_str:>8}  {correct:>4}")

    # New trade
    nt = results.get("new_trade_result")
    if nt and "error" not in nt:
        print()
        print(f"  NEW TRADE → {nt['ticker']} ({nt['direction']})")
        print(f"    Entry: ${nt['price_on_rec_date']:.2f} → "
              f"${nt['price_on_eval_date']:.2f}  "
              f"({nt['return_10d_pct']*100:+.2f}%)  "
              f"endpoint:{CORRECT_ICON.get(nt['trade_correct'], '?')}  "
              f"path:{CORRECT_ICON.get(nt.get('path_correct'), '?')}")
        # Fill-model realized P&L: shows the difference between "what the stock did"
        # and "what you actually net after slippage + commission".  This is the
        # authoritative edge number for attribution work.
        if nt.get("entry_fill_price") and nt.get("exit_fill_price"):
            print(f"    Fill P&L:      ${nt['entry_fill_price']:.2f} → "
                  f"${nt['exit_fill_price']:.2f}  "
                  f"gross {nt['realized_pnl_pct']*100:+.2f}%  "
                  f"net {nt['realized_pnl_pct_net']*100:+.2f}%  "
                  f"(exit: {nt.get('exit_reason', '?')})")
        stop_note   = f"stop hit day {nt['stop_hit_day']}"   if nt.get("stop_hit_during_period")   else "stop not hit"
        target_note = f"target hit day {nt['target_hit_day']}" if nt.get("target_hit_during_period") else "target not hit"
        print(f"    Path analysis: {stop_note} | {target_note}")
        # Multi-window comparison
        _mw_parts = []
        for w in EVAL_WINDOWS:
            key = f"return_{w}d_pct"
            if key in nt:
                _mw_parts.append(f"{w}d: {nt[key]*100:+.2f}%")
        if _mw_parts:
            print(f"    Multi-window:  {' | '.join(_mw_parts)}")

    # Summary
    s = results.get("summary", {})
    if s:
        print()
        print("  " + "-" * 68)
        print(f"  Direction:        {s['correct_calls']}/{s['total_evaluated']} "
              f"correct  ({s['accuracy_pct']}%)")
        if s.get("avg_hold_return_pct") is not None:
            sign = "+" if s['avg_hold_return_pct'] >= 0 else ""
            print(f"  HOLD positions:   avg 10d return {sign}{s['avg_hold_return_pct']:.2f}%  "
                  f"({s['hold_count']} positions)")
        if s.get("avg_exit_return_pct") is not None:
            sign = "+" if s['avg_exit_return_pct'] >= 0 else ""
            print(f"  EXIT/REDUCE:      price moved {sign}{s['avg_exit_return_pct']:.2f}% after exit  "
                  f"({s['exit_reduce_count']} positions)")
        if s.get("premature_exits", 0) > 0:
            print(f"  Premature exits:  {s['premature_exits']} position(s) rose after EXIT/REDUCE")
        if s.get("profit_lock_count", 0) > 0:
            tacc = s.get("timing_accuracy_pct")
            mfg  = s.get("median_foregone_gain_pct")
            tacc_str = f"{tacc}%" if tacc is not None else "N/A"
            mfg_str  = f"{mfg:+.2f}%" if mfg is not None else "N/A"
            print(f"  Profit-lock timing: {s.get('timing_correct_count', 0)}/"
                  f"{s['profit_lock_count']} near peak ({tacc_str}), "
                  f"median foregone gain {mfg_str}")
            print(f"                    (timing ≠ direction: a rule-fired REDUCE can be "
                  f"direction-correct yet still leave profit on the table)")

    print("=" * 72)
    print()


def aggregate_forward_tests(pattern=None):
    """Cross-file per-strategy rollup of new_trade realized P&L.

    Reads every `forward_test_*.json` that carries a `new_trade_result` with
    `realized_pnl_pct_net` (pre-P0-3 files without that field are skipped — they
    were produced under a different fill model and are not comparable).
    Historical files that predate the `strategy` echo bucket as 'unknown'.
    """
    from strategy_attribution import aggregate_by_strategy
    if pattern is None:
        pattern = os.path.join(DATA_DIR, "forward_test_*.json")
    trades = []
    for fp in sorted(glob.glob(pattern)):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            continue
        nt = r.get("new_trade_result") or {}
        if nt.get("realized_pnl_pct_net") is None:
            continue
        trades.append({
            "strategy":         nt.get("strategy") or "unknown",
            "pnl_pct_net":      nt["realized_pnl_pct_net"],
            "initial_risk_pct": nt.get("initial_risk_pct"),
        })
    return aggregate_by_strategy(trades)


def save_report(results, output_dir=DATA_DIR):
    """Save evaluation results to JSON."""
    date_str  = results["rec_date"].replace("-", "")
    out_path  = os.path.join(output_dir, f"forward_test_{date_str}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved forward test report to {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Forward-test LLM trading recommendations")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to a specific llm_output_YYYYMMDD.json file")
    parser.add_argument("--days", type=int, default=EVAL_DAYS,
                        help=f"Trading-day evaluation window (default: {EVAL_DAYS})")
    parser.add_argument("--aggregate", action="store_true",
                        help="Skip per-file eval; aggregate historical forward_test_*.json "
                             "into per-strategy attribution report.")
    args = parser.parse_args()

    if args.aggregate:
        from strategy_attribution import format_attribution_table
        by_strategy = aggregate_forward_tests()
        print("\n" + "=" * 72)
        print("  PER-STRATEGY ATTRIBUTION (forward_test_*.json)")
        print("=" * 72)
        print(format_attribution_table(by_strategy))
        print("=" * 72)
        out_path = os.path.join(
            DATA_DIR,
            f"strategy_attribution_{date.today().strftime('%Y%m%d')}.json")
        def _jsonable(v):
            if v == math.inf:
                return "inf"
            if v == -math.inf:
                return "-inf"
            return v
        serialisable = {
            k: {m: _jsonable(v) for m, v in mv.items()}
            for k, mv in by_strategy.items()
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(serialisable, f, indent=2, ensure_ascii=False)
        print(f"  Saved -> {out_path}\n")
        return

    if args.file:
        files = [args.file]
    else:
        # Pipeline saves advice as investment_advice_YYYYMMDD.json
        pattern = os.path.join(DATA_DIR, "investment_advice_*.json")
        files   = sorted(glob.glob(pattern))
        if not files:
            print(f"No investment_advice_*.json files found in {DATA_DIR}/")
            return

    evaluated = 0
    for filepath in files:
        logger.info(f"Evaluating {filepath} ...")
        results = evaluate_file(filepath, n_days=args.days)
        if results is None:
            continue   # Future date or parse error — already logged

        print_report(results)
        out_path = save_report(results)
        print(f"  Report saved → {out_path}\n")
        evaluated += 1

    if evaluated == 0:
        print(f"No files ready for evaluation yet "
              f"(need at least {args.days} trading days to have passed).")


if __name__ == "__main__":
    main()
