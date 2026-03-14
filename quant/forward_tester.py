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

EVAL_DAYS = 10          # Default trading-day window
DATA_DIR  = "data"


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


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def get_eval_date(rec_date, n_trading_days=EVAL_DAYS):
    """Return the date n business days after rec_date (approximate — ignores US holidays)."""
    dates = pd.bdate_range(start=rec_date + timedelta(days=1), periods=n_trading_days)
    return dates[-1].date()


def parse_date_from_filename(filepath):
    """Extract YYYYMMDD date from llm_output_YYYYMMDD.json filename."""
    basename = os.path.basename(filepath)
    # Expect: llm_output_YYYYMMDD.json
    stem = os.path.splitext(basename)[0]          # llm_output_YYYYMMDD
    date_str = stem.split("_")[-1]                # YYYYMMDD
    return datetime.strptime(date_str, "%Y%m%d").date()


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def action_is_correct(action, return_10d):
    """
    Determine if the recommendation was directionally correct.

    - EXIT / REDUCE: correct if price went DOWN  (protected capital)
    - HOLD:          correct if price went UP or flat
    - NEW TRADE:     correct if price went UP     (long trade wins)
    """
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
    with open(filepath, "r", encoding="utf-8") as f:
        llm_data = json.load(f)

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
        correct     = action_is_correct(action, return_10d)
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
            return_10d = (price_eval - price_rec) / price_rec
            correct    = action_is_correct("NEW TRADE", return_10d)
            results["new_trade_result"] = {
                "ticker":             ticker,
                "direction":          direction,
                "confidence":         confidence,
                "thesis":             new_trade.get("thesis"),
                "price_on_rec_date":  price_rec,
                "price_on_eval_date": price_eval,
                "return_10d_pct":     round(return_10d, 4),
                "trade_correct":      correct,
                "actual_rec_date":    str(date_rec),
                "actual_eval_date":   str(date_eval),
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
              f"{CORRECT_ICON.get(nt['trade_correct'], '?')}")

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
        pattern = os.path.join(DATA_DIR, "llm_output_*.json")
        files   = sorted(glob.glob(pattern))
        if not files:
            print(f"No llm_output_*.json files found in {DATA_DIR}/")
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
