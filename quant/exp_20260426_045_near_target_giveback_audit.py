"""Observed-only audit for near-target giveback bad trades.

This experiment does not change strategy behavior. It replays the accepted
stack on fixed OHLCV snapshots, then classifies trades whose intratrade high
approached the target or built meaningful MFE before ending as poor exits.
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


EXPERIMENT_ID = "exp-20260426-046"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_045_near_target_giveback_audit.json",
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


def _path_for_trade(snapshot: dict[str, list[dict]], trade: dict) -> list[dict]:
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
    if not all(isinstance(v, (int, float)) for v in (entry, stop, target_mult)):
        return None
    atr = (entry - stop) / ATR_STOP_MULT
    return entry + (target_mult * atr)


def _trade_diagnostics(trade: dict, snapshot: dict[str, list[dict]]) -> dict:
    entry = trade.get("entry_price")
    exit_price = trade.get("exit_price")
    target = _target_price(trade)
    rows = _path_for_trade(snapshot, trade)
    highs = [row.get("High") for row in rows if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in rows if isinstance(row.get("Low"), (int, float))]

    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = None
    mae_pct = None
    target_progress = None
    giveback_fraction = None
    target_gap_pct = None
    family = "not_bad_or_no_giveback"

    if isinstance(entry, (int, float)) and isinstance(max_high, (int, float)):
        mfe_pct = (max_high / entry) - 1.0
    if isinstance(entry, (int, float)) and isinstance(min_low, (int, float)):
        mae_pct = (min_low / entry) - 1.0
    if (
        isinstance(target, (int, float))
        and isinstance(entry, (int, float))
        and isinstance(max_high, (int, float))
        and target > entry
    ):
        target_progress = (max_high - entry) / (target - entry)
        target_gap_pct = (target / max_high) - 1.0 if max_high else None
    if (
        isinstance(entry, (int, float))
        and isinstance(exit_price, (int, float))
        and isinstance(mfe_pct, (int, float))
        and mfe_pct > 0
    ):
        final_return = (exit_price / entry) - 1.0
        giveback_fraction = (mfe_pct - final_return) / mfe_pct

    is_bad = (trade.get("pnl") or 0) <= 0
    near_target = (
        isinstance(target_progress, (int, float))
        and target_progress >= NEAR_TARGET_PROGRESS
    )
    full_giveback = (
        isinstance(mfe_pct, (int, float))
        and mfe_pct >= MEANINGFUL_MFE_PCT
        and isinstance(giveback_fraction, (int, float))
        and giveback_fraction >= FULL_GIVEBACK_FRACTION
    )

    if is_bad and near_target:
        family = "near_target_bad_giveback"
    elif is_bad and full_giveback:
        family = "big_mfe_bad_giveback"
    elif is_bad:
        family = "bad_no_large_giveback"
    elif near_target or full_giveback:
        family = "winner_collateral_giveback_like"

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
        "exit_price": exit_price,
        "stop_price": trade.get("stop_price"),
        "target_price_est": round(target, 4) if isinstance(target, (int, float)) else None,
        "max_high": max_high,
        "min_low": min_low,
        "mfe_pct": round(mfe_pct, 6) if isinstance(mfe_pct, (int, float)) else None,
        "mae_pct": round(mae_pct, 6) if isinstance(mae_pct, (int, float)) else None,
        "target_progress": (
            round(target_progress, 6)
            if isinstance(target_progress, (int, float))
            else None
        ),
        "target_gap_pct": (
            round(target_gap_pct, 6)
            if isinstance(target_gap_pct, (int, float))
            else None
        ),
        "giveback_fraction": (
            round(giveback_fraction, 6)
            if isinstance(giveback_fraction, (int, float))
            else None
        ),
        "hold_days_observed": len(rows),
        "family": family,
    }


def _summary(rows: list[dict]) -> dict:
    pnls = [row["pnl"] for row in rows if isinstance(row.get("pnl"), (int, float))]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "winner_count": sum(1 for p in pnls if p > 0),
        "loser_count": sum(1 for p in pnls if p <= 0),
    }


def _count(rows: list[dict], key: str) -> dict:
    return dict(sorted(Counter(row.get(key) or "unknown" for row in rows).items()))


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    result = _run_window(universe, cfg)
    snapshot = _load_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    rows = [
        _trade_diagnostics(trade, snapshot)
        for trade in result.get("trades", [])
    ]

    by_family = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)

    bad_giveback = [
        row for row in rows
        if row["family"] in {"near_target_bad_giveback", "big_mfe_bad_giveback"}
    ]
    collateral = [
        row for row in rows
        if row["family"] == "winner_collateral_giveback_like"
    ]

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "total_pnl": result.get("total_pnl"),
            "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
        },
        "thresholds": {
            "near_target_progress": NEAR_TARGET_PROGRESS,
            "meaningful_mfe_pct": MEANINGFUL_MFE_PCT,
            "full_giveback_fraction": FULL_GIVEBACK_FRACTION,
        },
        "family_counts": _count(rows, "family"),
        "strategy_counts_for_bad_giveback": _count(bad_giveback, "strategy"),
        "sector_counts_for_bad_giveback": _count(bad_giveback, "sector"),
        "summary_by_family": {
            family: _summary(items)
            for family, items in sorted(by_family.items())
        },
        "bad_giveback_rows": sorted(
            bad_giveback,
            key=lambda row: (row.get("pnl") or 0),
        ),
        "winner_collateral_rows": sorted(
            collateral,
            key=lambda row: (row.get("pnl") or 0),
            reverse=True,
        ),
    }


def main() -> int:
    universe = get_universe()
    windows = OrderedDict(
        (label, _window_audit(label, cfg, universe))
        for label, cfg in WINDOWS.items()
    )

    all_bad = [
        row
        for window in windows.values()
        for row in window["bad_giveback_rows"]
    ]
    all_collateral = [
        row
        for window in windows.values()
        for row in window["winner_collateral_rows"]
    ]
    all_trades = sum(
        window["metrics"]["trade_count"] or 0
        for window in windows.values()
    )

    aggregate = {
        "total_trades": all_trades,
        "bad_giveback_count": len(all_bad),
        "bad_giveback_pnl_sum": round(sum(row.get("pnl") or 0.0 for row in all_bad), 2),
        "winner_collateral_count": len(all_collateral),
        "winner_collateral_pnl_sum": round(
            sum(row.get("pnl") or 0.0 for row in all_collateral),
            2,
        ),
        "bad_giveback_strategy_counts": _count(all_bad, "strategy"),
        "bad_giveback_sector_counts": _count(all_bad, "sector"),
        "collateral_strategy_counts": _count(all_collateral, "strategy"),
        "collateral_sector_counts": _count(all_collateral, "sector"),
        "collateral_to_bad_count_ratio": (
            round(len(all_collateral) / len(all_bad), 4)
            if all_bad else None
        ),
        "collateral_to_bad_pnl_abs_ratio": (
            round(
                sum(row.get("pnl") or 0.0 for row in all_collateral)
                / abs(sum(row.get("pnl") or 0.0 for row in all_bad)),
                4,
            )
            if all_bad and sum(row.get("pnl") or 0.0 for row in all_bad) else None
        ),
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": (
            "near-target giveback failure taxonomy for accepted-stack bad trades"
        ),
        "hypothesis": (
            "Accepted-stack bad trades may contain a reproducible near-target "
            "giveback family where positions approached their target or built "
            "meaningful MFE before reversing into poor exits."
        ),
        "parameters": {
            "near_target_progress": NEAR_TARGET_PROGRESS,
            "meaningful_mfe_pct": MEANINGFUL_MFE_PCT,
            "full_giveback_fraction": FULL_GIVEBACK_FRACTION,
            "config": CONFIG,
        },
        "windows": windows,
        "aggregate": aggregate,
        "interpretation": {
            "decision": "observed_only",
            "finding": (
                "Near-target giveback is measurable as a lifecycle family, but "
                "winner collateral must be checked before any target-protection "
                "or partial-lock rule is tested."
            ),
            "next_alpha_implication": (
                "If the bad family is non-trivial and collateral is acceptable, "
                "the next test should be a shadow-mode partial-profit-lock replay "
                "only for trades that reach 75% target progress, not a generic "
                "weak-hold exit or target-widening rule."
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
