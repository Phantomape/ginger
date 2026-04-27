"""Observation-only oracle diagnostics for backtest results.

This module intentionally uses future prices. It is not a tradable strategy.
Its job is to estimate how much upside was available after the system had
already entered a trade, so we can separate exit/hold regret from entry alpha.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
except Exception:  # pragma: no cover - only used if constants import is broken.
    ROUND_TRIP_COST_PCT = 0.0035


def _load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def infer_snapshot_path(backtest_result):
    known = backtest_result.get("known_biases") or {}
    source = known.get("ohlcv_source") or {}
    return source.get("snapshot_path")


def _ohlcv_rows_by_date(snapshot):
    rows_by_ticker = {}
    for ticker, rows in (snapshot.get("ohlcv") or {}).items():
        rows_by_ticker[ticker.upper()] = {
            row.get("Date"): row
            for row in rows or []
            if row.get("Date")
        }
    return rows_by_ticker


def _window_rows(rows_by_date, entry_date, exit_date):
    if not entry_date or not exit_date:
        return []
    return [
        row for day, row in sorted(rows_by_date.items())
        if entry_date <= day <= exit_date
    ]


def _next_rows_after(rows_by_date, signal_date, horizon_days):
    dates = sorted(rows_by_date)
    eligible = [day for day in dates if day > signal_date]
    return [rows_by_date[day] for day in eligible[:horizon_days]]


def _oracle_exit_for_trade(trade, rows):
    entry_price = trade.get("entry_price")
    shares = trade.get("shares")
    if not entry_price or not shares or not rows:
        return None

    best_row = max(rows, key=lambda row: float(row.get("High") or 0))
    best_raw_high = float(best_row.get("High") or 0)
    if best_raw_high <= 0:
        return None

    # Match the backtester convention: entry_price already includes entry
    # slippage; exit cost is applied against the exit raw price.
    oracle_exit_price = best_raw_high * (1 - ROUND_TRIP_COST_PCT)
    oracle_pnl = (oracle_exit_price - entry_price) * shares
    actual_pnl = float(trade.get("pnl") or 0.0)
    regret = oracle_pnl - actual_pnl
    capture_ratio = actual_pnl / oracle_pnl if oracle_pnl > 0 else None

    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "actual_exit_date": trade.get("exit_date"),
        "oracle_exit_date": best_row.get("Date"),
        "entry_price": round(float(entry_price), 4),
        "actual_exit_price": trade.get("exit_price"),
        "oracle_exit_price": round(oracle_exit_price, 4),
        "shares": shares,
        "actual_pnl": round(actual_pnl, 2),
        "oracle_pnl": round(oracle_pnl, 2),
        "regret_vs_oracle": round(regret, 2),
        "capture_ratio": round(capture_ratio, 4) if capture_ratio is not None else None,
        "exit_reason": trade.get("exit_reason"),
    }


def _candidate_sources(backtest_result):
    sources = []
    for key in ("llm_gate_unreplayed", "news_veto_unreplayed"):
        bucket = (backtest_result.get("known_biases") or {}).get(key) or {}
        tickers_by_date = bucket.get("candidate_tickers_by_date") or {}
        if tickers_by_date:
            sources.append((key, tickers_by_date))
    return sources


def _collect_candidate_forward_rows(backtest_result, snapshot, horizon_days):
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    actual_trade_keys = {
        (trade.get("entry_date"), (trade.get("ticker") or "").upper())
        for trade in backtest_result.get("trades") or []
    }
    seen = set()
    candidate_rows = []
    missing = []

    for source, tickers_by_date in _candidate_sources(backtest_result):
        for raw_date, tickers in tickers_by_date.items():
            signal_date = (
                f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                if len(raw_date) == 8 and raw_date.isdigit() else raw_date
            )
            for ticker in tickers or []:
                ticker = (ticker or "").upper()
                key = (signal_date, ticker)
                if key in seen:
                    continue
                seen.add(key)
                rows = rows_by_ticker.get(ticker)
                if not rows:
                    missing.append({"signal_date": signal_date, "ticker": ticker, "reason": "missing_ohlcv"})
                    continue
                forward = _next_rows_after(rows, signal_date, horizon_days)
                if not forward:
                    missing.append({"signal_date": signal_date, "ticker": ticker, "reason": "no_forward_rows"})
                    continue

                entry_row = forward[0]
                entry_open = float(entry_row.get("Open") or 0)
                if entry_open <= 0:
                    missing.append({"signal_date": signal_date, "ticker": ticker, "reason": "invalid_entry_open"})
                    continue
                best_row = max(forward, key=lambda row: float(row.get("High") or 0))
                best_high = float(best_row.get("High") or 0)
                max_return = (best_high * (1 - ROUND_TRIP_COST_PCT) / entry_open) - 1
                candidate_rows.append({
                    "signal_date": signal_date,
                    "ticker": ticker,
                    "source": source,
                    "entry_date": entry_row.get("Date"),
                    "oracle_exit_date": best_row.get("Date"),
                    "entry_open": round(entry_open, 4),
                    "oracle_exit_price": round(best_high * (1 - ROUND_TRIP_COST_PCT), 4),
                    "max_forward_return_pct": round(max_return, 6),
                    "became_actual_trade_same_entry_day": (
                        (entry_row.get("Date"), ticker) in actual_trade_keys
                    ),
                })

    return candidate_rows, missing


def build_candidate_forward_oracle(backtest_result, snapshot, horizon_days=20):
    candidate_rows, missing = _collect_candidate_forward_rows(
        backtest_result,
        snapshot,
        horizon_days,
    )

    if not candidate_rows:
        return {
            "oracle_type": "candidate_forward_upper_bound",
            "is_tradable": False,
            "lookahead_warning": "Uses future highs after candidate dates; diagnostic only.",
            "horizon_days": horizon_days,
            "candidate_count": 0,
            "missing_candidate_count": len(missing),
            "missing_candidates": missing,
        }

    returns = [row["max_forward_return_pct"] for row in candidate_rows]
    top = sorted(candidate_rows, key=lambda row: row["max_forward_return_pct"], reverse=True)[:10]
    actual_overlap = sum(1 for row in candidate_rows if row["became_actual_trade_same_entry_day"])
    positive = sum(1 for r in returns if r > 0)

    return {
        "oracle_type": "candidate_forward_upper_bound",
        "is_tradable": False,
        "lookahead_warning": (
            "Uses future highs after candidate dates. This estimates candidate-pool opportunity, "
            "not achievable strategy PnL."
        ),
        "horizon_days": horizon_days,
        "candidate_count": len(candidate_rows),
        "missing_candidate_count": len(missing),
        "positive_candidate_fraction": round(positive / len(candidate_rows), 4),
        "actual_trade_overlap_count": actual_overlap,
        "actual_trade_overlap_fraction": round(actual_overlap / len(candidate_rows), 4),
        "avg_max_forward_return_pct": round(sum(returns) / len(returns), 6),
        "median_max_forward_return_pct": round(sorted(returns)[len(returns) // 2], 6),
        "best_max_forward_return_pct": round(max(returns), 6),
        "top_candidate_opportunities": top,
        "missing_candidates": missing,
    }


def build_candidate_selection_oracle(backtest_result, snapshot, horizon_days=20, k_values=(1, 2, 3)):
    candidate_rows, missing = _collect_candidate_forward_rows(
        backtest_result,
        snapshot,
        horizon_days,
    )
    if not candidate_rows:
        return {
            "oracle_type": "candidate_selection_upper_bound",
            "is_tradable": False,
            "lookahead_warning": "Uses future candidate returns for ranking; diagnostic only.",
            "horizon_days": horizon_days,
            "candidate_days": 0,
            "missing_candidate_count": len(missing),
            "missing_candidates": missing,
        }

    by_signal_date = {}
    for row in candidate_rows:
        by_signal_date.setdefault(row["signal_date"], []).append(row)

    actual_rows = [
        row for row in candidate_rows
        if row["became_actual_trade_same_entry_day"]
    ]
    actual_returns = [row["max_forward_return_pct"] for row in actual_rows]

    daily_rank_regrets = []
    missed_top1 = []
    top1_actual_hits = 0
    days_with_actual = 0

    for signal_date, rows in sorted(by_signal_date.items()):
        ranked = sorted(rows, key=lambda row: row["max_forward_return_pct"], reverse=True)
        top1 = ranked[0]
        actual_for_day = [
            row for row in rows
            if row["became_actual_trade_same_entry_day"]
        ]
        if top1["became_actual_trade_same_entry_day"]:
            top1_actual_hits += 1
        else:
            missed_top1.append(top1)
        if actual_for_day:
            days_with_actual += 1
            best_actual = max(actual_for_day, key=lambda row: row["max_forward_return_pct"])
            daily_rank_regrets.append({
                "signal_date": signal_date,
                "top_candidate": top1["ticker"],
                "top_candidate_return_pct": top1["max_forward_return_pct"],
                "best_actual_candidate": best_actual["ticker"],
                "best_actual_return_pct": best_actual["max_forward_return_pct"],
                "selection_regret_pct": round(
                    top1["max_forward_return_pct"] - best_actual["max_forward_return_pct"],
                    6,
                ),
            })

    top_k_summary = {}
    for k in k_values:
        selected = []
        for rows in by_signal_date.values():
            ranked = sorted(rows, key=lambda row: row["max_forward_return_pct"], reverse=True)
            selected.extend(ranked[:k])
        returns = [row["max_forward_return_pct"] for row in selected]
        top_k_summary[f"top_{k}"] = {
            "selected_candidate_count": len(selected),
            "equal_weight_avg_max_forward_return_pct": (
                round(sum(returns) / len(returns), 6) if returns else None
            ),
            "best_selected_return_pct": round(max(returns), 6) if returns else None,
            "worst_selected_return_pct": round(min(returns), 6) if returns else None,
        }

    regret_values = [row["selection_regret_pct"] for row in daily_rank_regrets]
    missed_top1 = sorted(
        missed_top1,
        key=lambda row: row["max_forward_return_pct"],
        reverse=True,
    )[:10]
    all_missed_top1 = [
        sorted(rows, key=lambda row: row["max_forward_return_pct"], reverse=True)[0]
        for rows in by_signal_date.values()
        if not any(row["became_actual_trade_same_entry_day"] for row in rows)
    ]
    missed_top1_returns = [
        row["max_forward_return_pct"]
        for row in all_missed_top1
    ]

    return {
        "oracle_type": "candidate_selection_upper_bound",
        "is_tradable": False,
        "lookahead_warning": (
            "Ranks candidates by future returns. Use only to estimate selection/ranking headroom, "
            "never as a tradable ranking rule."
        ),
        "horizon_days": horizon_days,
        "candidate_days": len(by_signal_date),
        "candidate_count": len(candidate_rows),
        "missing_candidate_count": len(missing),
        "days_with_actual_selection": days_with_actual,
        "days_without_actual_selection": len(by_signal_date) - days_with_actual,
        "top1_actual_hit_fraction": round(top1_actual_hits / len(by_signal_date), 4),
        "actual_selected_candidate_count": len(actual_rows),
        "actual_equal_weight_avg_max_forward_return_pct": (
            round(sum(actual_returns) / len(actual_returns), 6)
            if actual_returns else None
        ),
        "missed_top1_avg_max_forward_return_pct": (
            round(sum(missed_top1_returns) / len(missed_top1_returns), 6)
            if missed_top1_returns else None
        ),
        "avg_top1_vs_actual_selection_regret_pct": (
            round(sum(regret_values) / len(regret_values), 6)
            if regret_values else None
        ),
        "top_k_summary": top_k_summary,
        "largest_daily_selection_regrets": sorted(
            daily_rank_regrets,
            key=lambda row: row["selection_regret_pct"],
            reverse=True,
        )[:10],
        "missed_top1_opportunities": missed_top1,
        "missing_candidates": missing,
    }


def build_perfect_exit_oracle(backtest_result, snapshot):
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    trade_oracles = []
    missing = []

    for trade in backtest_result.get("trades") or []:
        ticker = (trade.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker)
        if not rows:
            missing.append({"ticker": ticker, "reason": "missing_ohlcv"})
            continue
        window = _window_rows(rows, trade.get("entry_date"), trade.get("exit_date"))
        oracle = _oracle_exit_for_trade(trade, window)
        if oracle is None:
            missing.append({"ticker": ticker, "reason": "insufficient_trade_or_price_data"})
            continue
        trade_oracles.append(oracle)

    actual_pnl = sum(t["actual_pnl"] for t in trade_oracles)
    oracle_pnl = sum(t["oracle_pnl"] for t in trade_oracles)
    regret = oracle_pnl - actual_pnl
    capture_ratio = actual_pnl / oracle_pnl if oracle_pnl > 0 else None

    by_strategy = {}
    for row in trade_oracles:
        rec = by_strategy.setdefault(row["strategy"], {
            "trade_count": 0,
            "actual_pnl": 0.0,
            "oracle_pnl": 0.0,
            "regret_vs_oracle": 0.0,
        })
        rec["trade_count"] += 1
        rec["actual_pnl"] += row["actual_pnl"]
        rec["oracle_pnl"] += row["oracle_pnl"]
        rec["regret_vs_oracle"] += row["regret_vs_oracle"]

    for rec in by_strategy.values():
        rec["actual_pnl"] = round(rec["actual_pnl"], 2)
        rec["oracle_pnl"] = round(rec["oracle_pnl"], 2)
        rec["regret_vs_oracle"] = round(rec["regret_vs_oracle"], 2)
        rec["capture_ratio"] = (
            round(rec["actual_pnl"] / rec["oracle_pnl"], 4)
            if rec["oracle_pnl"] > 0 else None
        )

    top_regrets = sorted(
        trade_oracles,
        key=lambda row: row["regret_vs_oracle"],
        reverse=True,
    )[:10]

    return {
        "oracle_type": "perfect_exit_after_actual_entry",
        "is_tradable": False,
        "lookahead_warning": (
            "Uses future intratrade highs. Use only as an upper-bound/regret diagnostic, "
            "never as a strategy acceptance metric."
        ),
        "trade_count": len(trade_oracles),
        "missing_trade_count": len(missing),
        "actual_pnl": round(actual_pnl, 2),
        "oracle_pnl": round(oracle_pnl, 2),
        "regret_vs_oracle": round(regret, 2),
        "capture_ratio": round(capture_ratio, 4) if capture_ratio is not None else None,
        "by_strategy": dict(sorted(by_strategy.items())),
        "top_regret_trades": top_regrets,
        "missing_trades": missing,
    }


def build_oracle_diagnostics(backtest_path, snapshot_path=None, candidate_horizon_days=20):
    backtest = _load_json(backtest_path)
    snapshot_path = snapshot_path or infer_snapshot_path(backtest)
    if not snapshot_path:
        raise ValueError("No OHLCV snapshot path found; pass --snapshot explicitly.")
    snapshot = _load_json(snapshot_path)

    return {
        "source_backtest": os.path.abspath(backtest_path),
        "source_snapshot": os.path.abspath(snapshot_path),
        "period": backtest.get("period"),
        "oracle_metrics": {
            "perfect_exit": build_perfect_exit_oracle(backtest, snapshot),
            "candidate_forward": build_candidate_forward_oracle(
                backtest,
                snapshot,
                horizon_days=candidate_horizon_days,
            ),
            "candidate_selection": build_candidate_selection_oracle(
                backtest,
                snapshot,
                horizon_days=candidate_horizon_days,
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest", required=True, help="Backtest result JSON.")
    parser.add_argument("--snapshot", help="OHLCV snapshot JSON. Defaults to known_biases path.")
    parser.add_argument(
        "--candidate-horizon-days",
        type=int,
        default=20,
        help="Trading-day horizon for candidate forward upper-bound diagnostics.",
    )
    parser.add_argument("--out", help="Optional output JSON path.")
    args = parser.parse_args()

    result = build_oracle_diagnostics(
        args.backtest,
        args.snapshot,
        candidate_horizon_days=args.candidate_horizon_days,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
