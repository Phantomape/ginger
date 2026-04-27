"""Observed-only context taxonomy for low-MFE stopouts.

This audit keeps strategy behavior unchanged. It narrows exp-20260426-052 by
classifying low-MFE stopout bad trades into reproducible entry/path contexts
and estimating winner collateral if those same contexts were later used as a
lifecycle response trigger.
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
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260426-055"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_055_low_mfe_context_audit.json",
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
ENTRY_AIR_POCKET_PCT = -0.025
DAY1_FLUSH_PCT = -0.03
NO_RECLAIM_PCT = 0.0


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
    return [row for row in rows if entry <= row.get("Date", "") <= exit_]


def _safe_return(price: float | None, base: float | None) -> float | None:
    if isinstance(price, (int, float)) and isinstance(base, (int, float)) and base > 0:
        return (price / base) - 1.0
    return None


def _diagnostics(trade: dict, snapshot: dict[str, list[dict]]) -> dict:
    rows = _trade_rows(snapshot, trade)
    entry = trade.get("entry_price")
    highs = [row.get("High") for row in rows if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in rows if isinstance(row.get("Low"), (int, float))]
    closes = [row.get("Close") for row in rows if isinstance(row.get("Close"), (int, float))]

    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = _safe_return(max_high, entry)
    mae_pct = _safe_return(min_low, entry)
    entry_close_return_pct = _safe_return(closes[0], entry) if closes else None
    day1_close_return_pct = _safe_return(closes[1], entry) if len(closes) > 1 else None
    first_three_close_peak_pct = _safe_return(max(closes[:3]), entry) if closes else None
    first_three_close_trough_pct = _safe_return(min(closes[:3]), entry) if closes else None
    hold_days_observed = len(rows)

    is_bad = (trade.get("pnl") or 0) <= 0
    low_mfe = isinstance(mfe_pct, (int, float)) and mfe_pct < LOW_MFE_PCT
    stopped = trade.get("exit_reason") == "stop"
    context = _context_label(
        hold_days_observed=hold_days_observed,
        entry_close_return_pct=entry_close_return_pct,
        day1_close_return_pct=day1_close_return_pct,
        first_three_close_peak_pct=first_three_close_peak_pct,
        mfe_pct=mfe_pct,
    )

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
        "mfe_pct": _round(mfe_pct),
        "mae_pct": _round(mae_pct),
        "entry_close_return_pct": _round(entry_close_return_pct),
        "day1_close_return_pct": _round(day1_close_return_pct),
        "first_three_close_peak_pct": _round(first_three_close_peak_pct),
        "first_three_close_trough_pct": _round(first_three_close_trough_pct),
        "hold_days_observed": hold_days_observed,
        "is_bad": is_bad,
        "is_winner": (trade.get("pnl") or 0) > 0,
        "is_low_mfe": low_mfe,
        "is_low_mfe_stopout_bad": is_bad and low_mfe and stopped,
        "low_mfe_context": context,
    }


def _round(value: float | None) -> float | None:
    return round(value, 6) if isinstance(value, (int, float)) else None


def _context_label(
    *,
    hold_days_observed: int,
    entry_close_return_pct: float | None,
    day1_close_return_pct: float | None,
    first_three_close_peak_pct: float | None,
    mfe_pct: float | None,
) -> str:
    if (
        hold_days_observed <= 1
        and isinstance(entry_close_return_pct, (int, float))
        and entry_close_return_pct <= ENTRY_AIR_POCKET_PCT
    ):
        return "same_day_entry_air_pocket"
    if isinstance(day1_close_return_pct, (int, float)) and day1_close_return_pct <= DAY1_FLUSH_PCT:
        return "day1_flush_after_entry"
    if (
        hold_days_observed >= 5
        and isinstance(first_three_close_peak_pct, (int, float))
        and first_three_close_peak_pct <= NO_RECLAIM_PCT
    ):
        return "multi_day_no_reclaim"
    if isinstance(mfe_pct, (int, float)) and 0 <= mfe_pct < LOW_MFE_PCT:
        return "micro_bounce_then_stop"
    return "other_low_mfe_context"


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


def _counter(rows: list[dict], key: str) -> dict:
    return dict(sorted(Counter(row.get(key) or "unknown" for row in rows).items()))


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    result = _run_window(universe, cfg)
    snapshot = _load_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    rows = [_diagnostics(trade, snapshot) for trade in result.get("trades", [])]
    low_mfe_bad = [row for row in rows if row["is_low_mfe_stopout_bad"]]
    context_names = sorted({row["low_mfe_context"] for row in low_mfe_bad})
    context_matched = [
        row for row in rows
        if row["low_mfe_context"] in context_names
    ]
    winner_collateral = [row for row in context_matched if row["is_winner"]]

    by_context = defaultdict(list)
    for row in low_mfe_bad:
        by_context[row["low_mfe_context"]].append(row)

    collateral_by_context = defaultdict(list)
    for row in winner_collateral:
        collateral_by_context[row["low_mfe_context"]].append(row)

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
        "low_mfe_bad_count": len(low_mfe_bad),
        "low_mfe_context_counts": _counter(low_mfe_bad, "low_mfe_context"),
        "low_mfe_strategy_counts": _counter(low_mfe_bad, "strategy"),
        "low_mfe_sector_counts": _counter(low_mfe_bad, "sector"),
        "summary_by_context": {
            context: _summary(items)
            for context, items in sorted(by_context.items())
        },
        "winner_collateral_by_context": {
            context: _summary(collateral_by_context.get(context, []))
            for context in context_names
        },
        "context_matched_winner_count": len(winner_collateral),
        "context_matched_winner_pnl_sum": round(sum(row.get("pnl") or 0.0 for row in winner_collateral), 2),
        "low_mfe_bad_rows": sorted(low_mfe_bad, key=lambda row: row.get("pnl") or 0),
        "winner_collateral_rows": sorted(
            winner_collateral,
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
    low_mfe_rows = [
        row
        for window in windows.values()
        for row in window["low_mfe_bad_rows"]
    ]
    collateral_rows = [
        row
        for window in windows.values()
        for row in window["winner_collateral_rows"]
    ]

    context_counts = Counter(row["low_mfe_context"] for row in low_mfe_rows)
    context_pnl = defaultdict(float)
    for row in low_mfe_rows:
        context_pnl[row["low_mfe_context"]] += row.get("pnl") or 0.0
    collateral_counts = Counter(row["low_mfe_context"] for row in collateral_rows)
    collateral_pnl = defaultdict(float)
    for row in collateral_rows:
        collateral_pnl[row["low_mfe_context"]] += row.get("pnl") or 0.0

    aggregate = {
        "total_low_mfe_stopout_bad_count": len(low_mfe_rows),
        "total_low_mfe_stopout_bad_pnl_sum": round(sum(context_pnl.values()), 2),
        "context_counts": dict(sorted(context_counts.items())),
        "context_pnl_sum": {
            context: round(value, 2)
            for context, value in sorted(context_pnl.items())
        },
        "context_matched_winner_collateral_count": len(collateral_rows),
        "context_matched_winner_collateral_pnl_sum": round(sum(collateral_pnl.values()), 2),
        "winner_collateral_counts_by_context": dict(sorted(collateral_counts.items())),
        "winner_collateral_pnl_by_context": {
            context: round(value, 2)
            for context, value in sorted(collateral_pnl.items())
        },
        "collateral_to_bad_count_ratio": (
            round(len(collateral_rows) / len(low_mfe_rows), 4)
            if low_mfe_rows else None
        ),
        "collateral_to_bad_pnl_abs_ratio": (
            round(sum(collateral_pnl.values()) / abs(sum(context_pnl.values())), 4)
            if context_pnl and sum(context_pnl.values()) else None
        ),
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "low-MFE stopout context taxonomy",
        "hypothesis": (
            "Low-MFE stopouts may cluster in reproducible entry/path contexts "
            "that explain why the broad family had zero observed winner collateral."
        ),
        "parameters": {
            "low_mfe_pct": LOW_MFE_PCT,
            "entry_air_pocket_pct": ENTRY_AIR_POCKET_PCT,
            "day1_flush_pct": DAY1_FLUSH_PCT,
            "multi_day_no_reclaim_peak_pct": NO_RECLAIM_PCT,
            "config": CONFIG,
        },
        "windows": windows,
        "aggregate": aggregate,
        "interpretation": {
            "decision": "observed_only",
            "finding": (
                "Low-MFE stopouts concentrate in a few observable path contexts, "
                "but context predicates also match profitable trades once the "
                "low-MFE final lifecycle condition is removed."
            ),
            "follow_up_recommendation": (
                "Do not convert this directly into a pre-entry filter. If tested, "
                "use a default-off lifecycle response keyed to persistent sub-1% "
                "MFE plus the narrowest context, and compare against winner "
                "collateral in a production-path replay."
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
