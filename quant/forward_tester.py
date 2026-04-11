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
            "stop_hit":       bool,
            "stop_hit_day":   int or None,      # trading day index (1-based)
            "stop_hit_price": float or None,    # low on the stop-hit day
            "target_hit":     bool,
            "target_hit_day": int or None,
            "data_available": bool,
        }
    """
    result = {
        "stop_hit":       False,
        "stop_hit_day":   None,
        "stop_hit_price": None,
        "target_hit":     False,
        "target_hit_day": None,
        "data_available": False,
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
            if open_p < stop_price:
                result["stop_hit_price"] = round(open_p, 4)    # gap-fill: execution at open
            else:
                result["stop_hit_price"] = round(stop_price, 4)  # intraday fill at stop

        # Target hit: daily High reaches or exceeds target_price
        if not result["target_hit"] and target_price and high >= target_price:
            result["target_hit"]     = True
            result["target_hit_day"] = day_idx

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

def action_is_correct(action, return_10d, exit_rule=None):
    """
    Determine if the recommendation was directionally correct.

    - EXIT:          correct if price went DOWN  (protected capital)
    - REDUCE (risk): correct if price went DOWN  (cut a losing/risky position)
    - REDUCE (profit-taking): always correct — rule-triggered profit lock at a
      planned level is correct regardless of subsequent price direction.
      Rules that lock in profits: PROFIT_TARGET, SIGNAL_TARGET, PROFIT_LADDER_50,
      PROFIT_LADDER_30.  Example: reducing NVDA at +20% (PROFIT_TARGET) is a
      correct decision even if NVDA subsequently rises to +30%.
    - HOLD:          correct if price went UP or flat
    - NEW TRADE:     correct if price went UP     (long trade wins)
    """
    PROFIT_LOCKING_RULES = {
        "PROFIT_TARGET", "SIGNAL_TARGET", "PROFIT_LADDER_50", "PROFIT_LADDER_30"
    }
    if action == "REDUCE" and exit_rule in PROFIT_LOCKING_RULES:
        # Profit-locking: rule fired at the planned target — always a correct execution
        return True
    if action in ("EXIT", "REDUCE"):
        return return_10d < 0
    elif action == "HOLD":
        return return_10d >= 0
    return None     # unknown action type


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

        results["position_results"].append({
            "ticker":            ticker,
            "action":            action,
            "exit_rule":         rule,
            "confidence":        confidence,
            "avg_cost":          avg_cost,
            "price_on_rec_date": price_rec,
            "pnl_vs_cost_pct":   round(pnl_vs_cost, 4) if pnl_vs_cost is not None else None,
            "price_on_eval_date":price_eval,
            "return_10d_pct":    round(return_10d, 4),
            "action_correct":    correct,
            "actual_rec_date":   str(date_rec),
            "actual_eval_date":  str(date_eval),
        })

    # ------------------------------------------------------------------
    # Evaluate new_trade (if any)
    # ------------------------------------------------------------------
    new_trade = llm_data.get("new_trade")
    if isinstance(new_trade, dict):
        ticker     = new_trade["ticker"]
        direction  = new_trade.get("direction", "long")
        confidence = new_trade.get("confidence")

        price_rec,  date_rec  = get_close_price(ticker, rec_date)
        price_eval, date_eval = get_close_price(ticker, eval_date)

        if price_rec is not None and price_eval is not None:
            return_10d      = (price_eval - price_rec) / price_rec
            # Deduct round-trip execution cost (0.35%) to evaluate net profitability.
            # Without cost: +0.2% looks "correct" for a long; actual net = -0.15% loss.
            # This matches the cost model in performance_engine.py and trade_advice.txt.
            ROUND_TRIP_COST = 0.0035
            net_return_10d  = return_10d - ROUND_TRIP_COST  # long trade: cost reduces gain
            correct         = action_is_correct("NEW TRADE", net_return_10d)

            # Path analysis: check if stop or target was hit DURING the evaluation window.
            # A trade that stops out on day 3 but recovers by day 10 shows as "correct"
            # using endpoint-only comparison — this is a false positive.
            stop_target_check = check_stop_or_target_hit(
                ticker       = ticker,
                entry_date   = rec_date,
                entry_price  = new_trade.get("entry_price") or price_rec,
                stop_price   = new_trade.get("stop_price"),
                target_price = new_trade.get("target_price"),
                n_days       = n_days,
            )
            # True profitability: if stop was hit first, the trade was a loss regardless
            # of where the price ended up at the 10-day mark.
            path_correct = correct
            if stop_target_check.get("data_available"):
                stop_day   = stop_target_check.get("stop_hit_day")
                target_day = stop_target_check.get("target_hit_day")
                if stop_target_check["stop_hit"] and (
                    not stop_target_check["target_hit"]
                    or (stop_day is not None and target_day is not None and stop_day < target_day)
                ):
                    # Stop was hit before (or without) target — actual trade result is a loss
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

            results["new_trade_result"] = {
                "ticker":              ticker,
                "direction":           direction,
                "confidence":          confidence,
                "thesis":              new_trade.get("thesis"),
                "price_on_rec_date":   price_rec,
                "price_on_eval_date":  price_eval,
                "return_10d_pct":      round(return_10d, 4),
                "net_return_10d_pct":  round(net_return_10d, 4),  # after 0.35% round-trip cost
                "trade_correct":       correct,        # endpoint-only (original metric)
                "path_correct":        path_correct,   # accounts for stop/target path
                "stop_hit_during_period":  stop_target_check.get("stop_hit", False),
                "stop_hit_day":            stop_target_check.get("stop_hit_day"),
                "target_hit_during_period": stop_target_check.get("target_hit", False),
                "target_hit_day":           stop_target_check.get("target_hit_day"),
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
        print(f"  Accuracy:         {s['correct_calls']}/{s['total_evaluated']} "
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

    print("=" * 72)
    print()


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
    args = parser.parse_args()

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
