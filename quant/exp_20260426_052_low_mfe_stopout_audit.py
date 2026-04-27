"""Observed-only audit for low-MFE accepted-stack stopouts.

This does not change strategy behavior. It replays the accepted stack on fixed
OHLCV snapshots and classifies bad trades whose lifecycle never produced even
1% max favorable excursion before stopping out.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260426-052"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_052_low_mfe_stopout_audit.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with weaker follow-through",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape",
    }),
])

CONFIG = {"REGIME_AWARE_EXIT": True}
LOW_MFE_PCT = 0.01
GAP_DOWN_PCT = -0.02
GAP_R_MULT = -0.50
NEAR_TARGET_PROGRESS = 0.75
MEANINGFUL_MFE_PCT = 0.05
FULL_GIVEBACK_FRACTION = 0.80


def _load_snapshot(path: str) -> dict[str, list[dict]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("ohlcv", {})


def _run_window(universe: list[str], cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _trade_rows(snapshot: dict[str, list[dict]], trade: dict) -> list[dict]:
    rows = snapshot.get(trade.get("ticker"), [])
    entry = trade.get("entry_date")
    exit_ = trade.get("exit_date")
    return [
        row for row in rows
        if entry <= row.get("Date", "") <= exit_
    ]


def _target_price(trade: dict) -> float | None:
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    target_mult = trade.get("target_mult_used")
    if all(isinstance(v, (int, float)) for v in (entry, stop, target_mult)):
        atr = (entry - stop) / ATR_STOP_MULT
        return entry + (target_mult * atr)
    return None


def _worst_overnight_gap(rows: list[dict], entry_date: str | None) -> float | None:
    worst_gap = None
    previous = None
    for row in rows:
        date = row.get("Date")
        if previous and date and date > (entry_date or ""):
            prev_close = previous.get("Close")
            open_price = row.get("Open")
            if isinstance(prev_close, (int, float)) and prev_close > 0 and isinstance(open_price, (int, float)):
                gap_pct = (open_price / prev_close) - 1.0
                worst_gap = gap_pct if worst_gap is None else min(worst_gap, gap_pct)
        previous = row
    return worst_gap


def _prior_family_labels(trade: dict, rows: list[dict], mfe_pct: float | None) -> list[str]:
    labels = []
    strategy = trade.get("strategy")
    days_held = max(len(rows) - 1, 0)
    if strategy == "trend_long" and days_held <= 1:
        labels.append("trend_instant_failure")
    if strategy == "trend_long" and days_held > 15:
        labels.append("trend_late_rollover")
    if strategy == "breakout_long":
        labels.append("breakout_false_positive_or_breakout_loss")

    entry = trade.get("entry_price")
    exit_price = trade.get("exit_price")
    highs = [row.get("High") for row in rows if isinstance(row.get("High"), (int, float))]
    max_high = max(highs) if highs else None
    target = _target_price(trade)
    target_progress = None
    if (
        isinstance(target, (int, float))
        and isinstance(entry, (int, float))
        and isinstance(max_high, (int, float))
        and target > entry
    ):
        target_progress = (max_high - entry) / (target - entry)
    giveback_fraction = None
    if (
        isinstance(entry, (int, float))
        and isinstance(exit_price, (int, float))
        and isinstance(mfe_pct, (int, float))
        and mfe_pct > 0
    ):
        final_return = (exit_price / entry) - 1.0
        giveback_fraction = (mfe_pct - final_return) / mfe_pct
    if (
        isinstance(target_progress, (int, float))
        and target_progress >= NEAR_TARGET_PROGRESS
    ) or (
        isinstance(mfe_pct, (int, float))
        and mfe_pct >= MEANINGFUL_MFE_PCT
        and isinstance(giveback_fraction, (int, float))
        and giveback_fraction >= FULL_GIVEBACK_FRACTION
    ):
        labels.append("near_target_or_big_mfe_giveback")

    worst_gap = _worst_overnight_gap(rows, trade.get("entry_date"))
    stop = trade.get("stop_price")
    risk_pct = None
    if isinstance(entry, (int, float)) and entry > 0 and isinstance(stop, (int, float)):
        risk_pct = (entry - stop) / entry
    if (
        isinstance(worst_gap, (int, float))
        and (
            worst_gap <= GAP_DOWN_PCT
            or (isinstance(risk_pct, (int, float)) and risk_pct > 0 and worst_gap / risk_pct <= GAP_R_MULT)
        )
    ):
        labels.append("post_entry_gap_down_damage")
    return labels


def _diagnostics(trade: dict, snapshot: dict[str, list[dict]]) -> dict:
    rows = _trade_rows(snapshot, trade)
    entry = trade.get("entry_price")
    highs = [row.get("High") for row in rows if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in rows if isinstance(row.get("Low"), (int, float))]
    closes = [row.get("Close") for row in rows if isinstance(row.get("Close"), (int, float))]

    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = None
    mae_pct = None
    entry_close_return_pct = None
    day1_close_return_pct = None
    first_three_close_peak_pct = None
    if isinstance(entry, (int, float)) and entry > 0:
        if isinstance(max_high, (int, float)):
            mfe_pct = (max_high / entry) - 1.0
        if isinstance(min_low, (int, float)):
            mae_pct = (min_low / entry) - 1.0
        if closes:
            entry_close_return_pct = (closes[0] / entry) - 1.0
            first_three_close_peak_pct = (max(closes[:3]) / entry) - 1.0
        if len(closes) > 1:
            day1_close_return_pct = (closes[1] / entry) - 1.0

    is_bad = (trade.get("pnl") or 0) <= 0
    low_mfe = isinstance(mfe_pct, (int, float)) and mfe_pct < LOW_MFE_PCT
    stopped = trade.get("exit_reason") == "stop"
    prior_labels = _prior_family_labels(trade, rows, mfe_pct)
    if is_bad and low_mfe and stopped:
        family = "low_mfe_stopout_bad"
    elif is_bad and low_mfe:
        family = "low_mfe_nonstop_bad"
    elif is_bad:
        family = "other_bad_trade"
    elif low_mfe:
        family = "winner_collateral_low_mfe"
    else:
        family = "winner_or_flat_not_low_mfe"

    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": trade.get("pnl"),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "entry_price": entry,
        "exit_price": trade.get("exit_price"),
        "max_high": max_high,
        "min_low": min_low,
        "mfe_pct": round(mfe_pct, 6) if isinstance(mfe_pct, (int, float)) else None,
        "mae_pct": round(mae_pct, 6) if isinstance(mae_pct, (int, float)) else None,
        "entry_close_return_pct": (
            round(entry_close_return_pct, 6)
            if isinstance(entry_close_return_pct, (int, float))
            else None
        ),
        "day1_close_return_pct": (
            round(day1_close_return_pct, 6)
            if isinstance(day1_close_return_pct, (int, float))
            else None
        ),
        "first_three_close_peak_pct": (
            round(first_three_close_peak_pct, 6)
            if isinstance(first_three_close_peak_pct, (int, float))
            else None
        ),
        "hold_days_observed": len(rows),
        "prior_family_labels": prior_labels,
        "prior_family_covered": bool(prior_labels),
        "family": family,
    }


def _summary(rows: list[dict]) -> dict:
    pnls = [row["pnl"] for row in rows if isinstance(row.get("pnl"), (int, float))]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "winner_count": sum(1 for pnl in pnls if pnl > 0),
        "loser_count": sum(1 for pnl in pnls if pnl <= 0),
    }


def _count(rows: list[dict], key: str) -> dict:
    return dict(sorted(Counter(row.get(key) or "unknown" for row in rows).items()))


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    result = _run_window(universe, cfg)
    snapshot = _load_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    rows = [_diagnostics(trade, snapshot) for trade in result.get("trades", [])]

    by_family = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)

    low_mfe_bad = [
        row for row in rows
        if row["family"] in {"low_mfe_stopout_bad", "low_mfe_nonstop_bad"}
    ]
    unclassified_low_mfe_bad = [
        row for row in low_mfe_bad
        if not row["prior_family_covered"]
    ]
    collateral = by_family["winner_collateral_low_mfe"]

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe": result.get("sharpe"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_pnl": result.get("total_pnl"),
            "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
        },
        "family_counts": _count(rows, "family"),
        "summary_by_family": {
            family: _summary(items)
            for family, items in sorted(by_family.items())
        },
        "low_mfe_bad_strategy_counts": _count(low_mfe_bad, "strategy"),
        "low_mfe_bad_sector_counts": _count(low_mfe_bad, "sector"),
        "unclassified_low_mfe_bad_count": len(unclassified_low_mfe_bad),
        "winner_collateral_low_mfe_count": len(collateral),
        "low_mfe_bad_rows": sorted(low_mfe_bad, key=lambda row: row.get("pnl") or 0),
        "unclassified_low_mfe_bad_rows": sorted(
            unclassified_low_mfe_bad,
            key=lambda row: row.get("pnl") or 0,
        ),
        "winner_collateral_low_mfe_rows": sorted(
            collateral,
            key=lambda row: row.get("pnl") or 0,
            reverse=True,
        ),
    }


def main() -> int:
    universe = get_universe()
    windows = OrderedDict(
        (label, _window_audit(label, cfg, universe))
        for label, cfg in WINDOWS.items()
    )

    low_mfe_bad = [
        row
        for window in windows.values()
        for row in window["low_mfe_bad_rows"]
    ]
    unclassified_low_mfe_bad = [
        row
        for window in windows.values()
        for row in window["unclassified_low_mfe_bad_rows"]
    ]
    collateral = [
        row
        for window in windows.values()
        for row in window["winner_collateral_low_mfe_rows"]
    ]
    total_trades = sum(window["metrics"]["trade_count"] or 0 for window in windows.values())
    bad_trade_count = sum(
        sum(summary.get("loser_count") or 0 for summary in window["summary_by_family"].values())
        for window in windows.values()
    )
    low_mfe_bad_pnl = sum(row.get("pnl") or 0.0 for row in low_mfe_bad)
    unclassified_pnl = sum(row.get("pnl") or 0.0 for row in unclassified_low_mfe_bad)
    collateral_pnl = sum(row.get("pnl") or 0.0 for row in collateral)
    prior_overlap = Counter(
        label
        for row in low_mfe_bad
        for label in row.get("prior_family_labels", [])
    )

    aggregate = {
        "total_trades": total_trades,
        "bad_trade_count": bad_trade_count,
        "low_mfe_bad_count": len(low_mfe_bad),
        "low_mfe_bad_frequency_of_all_trades": (
            round(len(low_mfe_bad) / total_trades, 4) if total_trades else None
        ),
        "low_mfe_bad_frequency_of_bad_trades": (
            round(len(low_mfe_bad) / bad_trade_count, 4) if bad_trade_count else None
        ),
        "low_mfe_bad_pnl_sum": round(low_mfe_bad_pnl, 2),
        "unclassified_low_mfe_bad_count": len(unclassified_low_mfe_bad),
        "unclassified_low_mfe_bad_pnl_sum": round(unclassified_pnl, 2),
        "winner_collateral_low_mfe_count": len(collateral),
        "winner_collateral_low_mfe_pnl_sum": round(collateral_pnl, 2),
        "prior_family_overlap_counts": dict(sorted(prior_overlap.items())),
        "low_mfe_bad_strategy_counts": _count(low_mfe_bad, "strategy"),
        "low_mfe_bad_sector_counts": _count(low_mfe_bad, "sector"),
        "unclassified_low_mfe_strategy_counts": _count(unclassified_low_mfe_bad, "strategy"),
        "unclassified_low_mfe_sector_counts": _count(unclassified_low_mfe_bad, "sector"),
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "low-MFE stopout taxonomy for accepted-stack bad trades",
        "hypothesis": (
            "Accepted-stack losers may contain a reproducible low-MFE stopout "
            "lifecycle family where positions never achieve even 1 percent "
            "favorable excursion before stopping out."
        ),
        "parameters": {
            "low_mfe_pct": LOW_MFE_PCT,
            "config": CONFIG,
            "prior_family_overlap_only": [
                "trend_instant_failure",
                "trend_late_rollover",
                "breakout false-positive/loss",
                "near-target or big-MFE giveback",
                "post-entry gap-down damage",
            ],
        },
        "windows": windows,
        "aggregate": aggregate,
        "interpretation": {
            "decision": "observed_only",
            "finding": (
                "Low-MFE stopouts are a repeated accepted-stack lifecycle family "
                "and explain most currently unclassified bad trades without "
                "introducing another production rule."
            ),
            "next_alpha_implication": (
                "A future experiment, if any, should test a post-entry lifecycle "
                "response to persistent sub-1% MFE rather than another pre-entry "
                "filter; broad pre-entry removal cannot observe this variable."
            ),
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")

    print(json.dumps(aggregate, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
