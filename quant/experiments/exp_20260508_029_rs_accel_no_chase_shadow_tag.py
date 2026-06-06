"""exp-20260508-029: RS acceleration + no-gap-chase shadow tag audit.

Lane: alpha_discovery (observed_only).
Change type: observed_only_shadow_tag_audit.
Single causal variable: rs_accel_no_chase candidate shadow tag.

Hypothesis
----------
Existing trend_long and breakout_long core candidate rows with BOTH:
  (a) improving 20-day SPY-relative strength (rs_current > rs_prior), AND
  (b) no signal-day gap chase (|open/prev_close - 1| <= 3%)
may identify cleaner continuation candidates with better forward replacement
value. This round is shadow-only and does not change ranking, sizing,
exits, or production logic.

Method (read-only, PIT)
-----------------------
- Load OHLCV from the canonical three-window JSON snapshots.
- Load closed trade records from the accepted canonical baseline artifacts
  (exp-20260602-003 window artifacts: late_strong_after.json, etc.).
- For each closed trade, compute at signal_date (= entry_date):
    rs_current = ticker_ret20 - spy_ret20
    rs_prior   = ticker_ret20 shifted 20 trading days earlier - spy_ret20_shifted
    rs_accel   = rs_current > rs_prior
    gap_pct    = open[signal_date] / close[signal_date - 1 day] - 1
    no_chase   = |gap_pct| <= 0.03
    tagged     = rs_accel AND no_chase
- Compare: tagged vs. untagged trade forward returns (pnl, pnl_pct, win rate).
- Produce per-window and pooled attribution artifact.

Acceptance boundary
-------------------
observed_only; no production promotion without a separate Gate 1-4 backtest.
Materiality bars: tagged average PnL lift > $500 AND average return lift > 5pp.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260508-029"
RULE_VERSION = "rs_accel_no_chase_shadow_tag_v1"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        # Canonical baseline: EV 5.1628, 18 trades
        "backtest": "data/backtests/backtest_results_20260603.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        # Canonical baseline: EV 2.1402, 21 trades
        "backtest": "data/backtests/backtest_results_20260522.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        # Canonical baseline: EV 0.5911, 22 trades
        "backtest": "data/backtests/backtest_results_20260517.json",
    },
}

# Thresholds
GAP_CHASE_THRESHOLD = 0.03      # 3% signal-day gap -> disqualify
RS_LOOKBACK = 20                # trading days for ret20
MATERIALITY_PNL_LIFT = 500.0   # $500 per trade minimum materiality
MATERIALITY_RETURN_LIFT = 0.05  # 5pp minimum materiality

OUTPUT_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260508-029"
OUTPUT_FILE = OUTPUT_DIR / "exp_20260508_029_rs_accel_no_chase_shadow_tag.json"


def _load_ohlcv(path: Path) -> dict[str, list[dict]]:
    """Return {ticker: [{"Date": str, "Open": float, "Close": float, ...}]}."""
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw["ohlcv"]


def _build_price_index(
    ohlcv: dict[str, list[dict]],
) -> dict[str, dict[str, dict]]:
    """Build {ticker: {date_str: row}} for fast lookup."""
    idx: dict[str, dict[str, dict]] = {}
    for ticker, rows in ohlcv.items():
        by_date: dict[str, dict] = {}
        for row in rows:
            by_date[row["Date"]] = row
        idx[ticker] = by_date
    return idx


def _sorted_dates(by_date: dict[str, dict]) -> list[str]:
    return sorted(by_date.keys())


def _prev_date(dates: list[str], target: str) -> str | None:
    """Return the trading day immediately before target in dates."""
    try:
        i = dates.index(target)
    except ValueError:
        # target not in list; find latest date <= target
        candidates = [d for d in dates if d < target]
        if not candidates:
            return None
        return max(candidates)
    return dates[i - 1] if i > 0 else None


def _date_n_before(dates: list[str], target: str, n: int) -> str | None:
    """Return the trading day n positions before target."""
    try:
        i = dates.index(target)
    except ValueError:
        candidates = [d for d in dates if d <= target]
        if not candidates:
            return None
        idx = dates.index(max(candidates))
        i = idx
    if i < n:
        return None
    return dates[i - n]


def _ret(by_date: dict[str, dict], dates: list[str], date_end: str, lookback: int) -> float | None:
    """Close-to-close return over lookback trading days ending at date_end."""
    date_start = _date_n_before(dates, date_end, lookback)
    if date_start is None:
        return None
    c_end = by_date[date_end]["Close"]
    c_start = by_date[date_start]["Close"]
    if c_start <= 0 or c_end <= 0:
        return None
    return c_end / c_start - 1.0


def _compute_tag(
    ticker: str,
    signal_date: str,
    price_idx: dict[str, dict[str, dict]],
    spy_dates: list[str],
) -> dict[str, Any]:
    """Compute rs_accel and no_chase tags for a single trade."""
    result: dict[str, Any] = {
        "ticker": ticker,
        "signal_date": signal_date,
        "rs_accel": None,
        "rs_current": None,
        "rs_prior": None,
        "no_chase": None,
        "gap_pct": None,
        "tagged": False,
        "skip_reason": None,
    }

    ticker_data = price_idx.get(ticker.upper())
    spy_data = price_idx.get("SPY")
    if ticker_data is None:
        result["skip_reason"] = "ticker_not_in_snapshot"
        return result
    if spy_data is None:
        result["skip_reason"] = "spy_not_in_snapshot"
        return result

    t_dates = _sorted_dates(ticker_data)

    # Find the effective signal date (closest trading day <= signal_date)
    if signal_date not in ticker_data:
        candidates = [d for d in t_dates if d <= signal_date]
        if not candidates:
            result["skip_reason"] = "signal_date_before_data"
            return result
        eff_signal_date = max(candidates)
    else:
        eff_signal_date = signal_date

    # RS current: ticker_ret20 - spy_ret20 at eff_signal_date
    t_ret20 = _ret(ticker_data, t_dates, eff_signal_date, RS_LOOKBACK)
    s_ret20 = _ret(spy_data, spy_dates, eff_signal_date, RS_LOOKBACK)
    if t_ret20 is None or s_ret20 is None:
        result["skip_reason"] = "insufficient_history_current"
        return result
    rs_current = t_ret20 - s_ret20

    # RS prior: same but shifted 20 trading days earlier
    prior_date = _date_n_before(t_dates, eff_signal_date, RS_LOOKBACK)
    if prior_date is None:
        result["skip_reason"] = "insufficient_history_prior"
        return result

    t_ret20_prior = _ret(ticker_data, t_dates, prior_date, RS_LOOKBACK)
    s_ret20_prior = _ret(spy_data, spy_dates, prior_date, RS_LOOKBACK)
    if t_ret20_prior is None or s_ret20_prior is None:
        result["skip_reason"] = "insufficient_history_prior_spy"
        return result
    rs_prior = t_ret20_prior - s_ret20_prior

    rs_accel = rs_current > rs_prior

    # Gap check: signal-day open vs. prior-day close
    prev_date = _prev_date(t_dates, eff_signal_date)
    if prev_date is None or prev_date not in ticker_data:
        result["skip_reason"] = "no_prior_day"
        return result
    prev_close = ticker_data[prev_date]["Close"]
    sig_open = ticker_data[eff_signal_date]["Open"]
    if prev_close <= 0:
        result["skip_reason"] = "zero_prev_close"
        return result
    gap_pct = sig_open / prev_close - 1.0
    no_chase = abs(gap_pct) <= GAP_CHASE_THRESHOLD

    result["rs_accel"] = bool(rs_accel)
    result["rs_current"] = round(rs_current, 6)
    result["rs_prior"] = round(rs_prior, 6)
    result["no_chase"] = bool(no_chase)
    result["gap_pct"] = round(gap_pct, 6)
    result["tagged"] = bool(rs_accel and no_chase)
    return result


def _analyze_window(
    window_name: str,
    cfg: dict,
) -> dict[str, Any]:
    snapshot_path = REPO_ROOT / cfg["snapshot"]
    backtest_path = REPO_ROOT / cfg["backtest"]

    if not snapshot_path.exists():
        return {"window": window_name, "error": f"snapshot not found: {cfg['snapshot']}"}
    if not backtest_path.exists():
        return {"window": window_name, "error": f"backtest not found: {cfg['backtest']}"}

    ohlcv = _load_ohlcv(snapshot_path)
    price_idx = _build_price_index(ohlcv)
    spy_dates = _sorted_dates(price_idx.get("SPY", {}))

    with backtest_path.open(encoding="utf-8") as fh:
        bt = json.load(fh)
    trades = bt.get("trades", [])

    tagged_trades: list[dict] = []
    untagged_trades: list[dict] = []
    skipped: list[dict] = []

    for trade in trades:
        ticker = trade.get("ticker", "")
        signal_date = trade.get("entry_date", "")
        pnl = trade.get("pnl", 0.0)
        pnl_pct = trade.get("pnl_pct_net", 0.0)
        exit_reason = trade.get("exit_reason", "")

        tag_result = _compute_tag(ticker, signal_date, price_idx, spy_dates)

        enriched = {
            "ticker": ticker,
            "signal_date": signal_date,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            **tag_result,
        }

        if tag_result.get("skip_reason"):
            skipped.append(enriched)
        elif tag_result.get("tagged"):
            tagged_trades.append(enriched)
        else:
            untagged_trades.append(enriched)

    def _stats(group: list[dict]) -> dict:
        if not group:
            return {"count": 0, "mean_pnl": None, "mean_ret_pct": None, "win_rate": None}
        pnls = [t["pnl"] for t in group]
        rets = [t["pnl_pct"] * 100 for t in group]  # convert to pct
        wins = sum(1 for p in pnls if p > 0)
        return {
            "count": len(group),
            "mean_pnl": round(statistics.mean(pnls), 2),
            "mean_ret_pct": round(statistics.mean(rets), 4),
            "win_rate": round(wins / len(group), 4),
            "total_pnl": round(sum(pnls), 2),
        }

    tagged_stats = _stats(tagged_trades)
    untagged_stats = _stats(untagged_trades)

    pnl_lift = None
    ret_lift = None
    if tagged_stats["mean_pnl"] is not None and untagged_stats["mean_pnl"] is not None:
        pnl_lift = round(tagged_stats["mean_pnl"] - untagged_stats["mean_pnl"], 2)
        ret_lift = round(tagged_stats["mean_ret_pct"] - untagged_stats["mean_ret_pct"], 4)

    materiality_ok = (
        pnl_lift is not None
        and ret_lift is not None
        and pnl_lift > MATERIALITY_PNL_LIFT
        and ret_lift > MATERIALITY_RETURN_LIFT * 100
    )

    return {
        "window": window_name,
        "start": cfg["start"],
        "end": cfg["end"],
        "total_trades": len(trades),
        "tagged_count": len(tagged_trades),
        "untagged_count": len(untagged_trades),
        "skipped_count": len(skipped),
        "tagged_share": round(len(tagged_trades) / len(trades), 4) if trades else None,
        "tagged_stats": tagged_stats,
        "untagged_stats": untagged_stats,
        "pnl_lift_tagged_vs_untagged": pnl_lift,
        "ret_lift_pct_tagged_vs_untagged": ret_lift,
        "materiality_ok": materiality_ok,
        "rs_accel_only_count": sum(1 for t in untagged_trades if t.get("rs_accel") and not t.get("no_chase")),
        "no_chase_only_count": sum(1 for t in untagged_trades if not t.get("rs_accel") and t.get("no_chase")),
        "neither_count": sum(1 for t in untagged_trades if not t.get("rs_accel") and not t.get("no_chase")),
        "tagged_tickers": [t["ticker"] for t in tagged_trades],
        "untagged_tickers": [t["ticker"] for t in untagged_trades],
        "skipped_tickers": [(t["ticker"], t.get("skip_reason")) for t in skipped],
        "tagged_trade_detail": [
            {k: t[k] for k in ["ticker", "signal_date", "pnl", "pnl_pct", "exit_reason",
                                "rs_current", "rs_prior", "gap_pct", "tagged"]}
            for t in tagged_trades
        ],
    }


def run() -> dict[str, Any]:
    window_results = {}
    for wname, cfg in WINDOWS.items():
        window_results[wname] = _analyze_window(wname, cfg)

    # Pooled stats across all windows
    all_tagged: list[dict] = []
    all_untagged: list[dict] = []
    for wr in window_results.values():
        if "error" not in wr:
            # Reconstruct from stats (we have per-window counts)
            pass  # We'll compute from window-level stats

    # Weighted pooled from window-level aggregates
    total_tagged = sum(wr.get("tagged_count", 0) for wr in window_results.values() if "error" not in wr)
    total_untagged = sum(wr.get("untagged_count", 0) for wr in window_results.values() if "error" not in wr)
    total_trades = total_tagged + total_untagged

    # Pooled PnL lift (simple average of window lifts, weights by count)
    lifts = [
        (wr["pnl_lift_tagged_vs_untagged"], wr["tagged_count"])
        for wr in window_results.values()
        if "error" not in wr and wr.get("pnl_lift_tagged_vs_untagged") is not None
    ]
    pooled_pnl_lift = None
    if lifts:
        total_tagged_in_lifts = sum(c for _, c in lifts)
        if total_tagged_in_lifts > 0:
            pooled_pnl_lift = round(sum(l * c for l, c in lifts) / total_tagged_in_lifts, 2)

    ret_lifts = [
        (wr["ret_lift_pct_tagged_vs_untagged"], wr["tagged_count"])
        for wr in window_results.values()
        if "error" not in wr and wr.get("ret_lift_pct_tagged_vs_untagged") is not None
    ]
    pooled_ret_lift = None
    if ret_lifts:
        total_tagged_in_ret_lifts = sum(c for _, c in ret_lifts)
        if total_tagged_in_ret_lifts > 0:
            pooled_ret_lift = round(sum(l * c for l, c in ret_lifts) / total_tagged_in_ret_lifts, 4)

    positive_windows = sum(
        1 for wr in window_results.values()
        if "error" not in wr and wr.get("pnl_lift_tagged_vs_untagged") is not None
        and wr["pnl_lift_tagged_vs_untagged"] > 0
    )
    windows_with_data = sum(1 for wr in window_results.values() if "error" not in wr and wr.get("pnl_lift_tagged_vs_untagged") is not None)

    materiality_pooled = (
        pooled_pnl_lift is not None
        and pooled_ret_lift is not None
        and pooled_pnl_lift > MATERIALITY_PNL_LIFT
        and pooled_ret_lift > MATERIALITY_RETURN_LIFT * 100
    )

    if materiality_pooled and positive_windows == windows_with_data:
        decision = "observed_positive_rs_accel_no_chase_worth_gate4"
    elif pooled_pnl_lift is not None and pooled_pnl_lift > 0 and positive_windows >= math.ceil(windows_with_data / 2):
        decision = "observed_positive_but_below_materiality"
    else:
        decision = "observed_no_robust_rs_accel_no_chase_edge"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": decision,
        "hypothesis": (
            "trend_long and breakout_long candidates with improving 20d SPY-relative "
            "strength AND no signal-day 3% gap chase (rs_accel_no_chase) may have "
            "better forward returns than the remaining core candidates."
        ),
        "single_causal_variable": "rs_accel_no_chase shadow tag (rs_accel=True AND no_chase=True)",
        "baseline_source": "exp-20260602-003 canonical three-window artifacts",
        "materiality_gates": {
            "min_pnl_lift_per_trade": MATERIALITY_PNL_LIFT,
            "min_return_lift_pct": MATERIALITY_RETURN_LIFT * 100,
        },
        "pooled_summary": {
            "total_tagged": total_tagged,
            "total_untagged": total_untagged,
            "total_trades": total_trades,
            "tagged_share": round(total_tagged / total_trades, 4) if total_trades else None,
            "pooled_pnl_lift": pooled_pnl_lift,
            "pooled_ret_lift_pct": pooled_ret_lift,
            "positive_windows": f"{positive_windows}/{windows_with_data}",
            "materiality_passed": materiality_pooled,
        },
        "window_results": window_results,
        "notes": [
            "Read-only attribution only. Does not change entries, exits, ranking, sizing, or orders.",
            "Signal_date = entry_date (canonical backtester entry_date is the signal day, execution is next open).",
            "RS acceleration: 20d SPY-relative return improved from 20 days prior to signal_date.",
            "No-chase: signal-day open vs. prior-day close gap ≤ 3%.",
            "Baseline trades from canonical single-window backtest results matching exp-20260602-003 EV baseline.",
            "OHLCV from three canonical snapshot JSON files (not warehouse).",
        ],
        "promotion_gate": (
            "observed_only. A positive result here justifies a separate Gate 1-4 experiment "
            "that tests the rs_accel_no_chase tag as a paper sleeve support field or entry "
            "discriminator using the canonical warehouse-backed backtest protocol."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


if __name__ == "__main__":
    result = run()
    summary = {
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "pooled_summary": result["pooled_summary"],
        "window_results": {
            w: {
                "tagged_count": r.get("tagged_count"),
                "untagged_count": r.get("untagged_count"),
                "pnl_lift": r.get("pnl_lift_tagged_vs_untagged"),
                "ret_lift_pct": r.get("ret_lift_pct_tagged_vs_untagged"),
                "materiality_ok": r.get("materiality_ok"),
            }
            for w, r in result["window_results"].items()
        },
    }
    print(json.dumps(summary, indent=2))
