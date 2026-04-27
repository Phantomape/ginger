"""Observed-only audit for post-entry sector-relative breakdown.

This experiment keeps strategy behavior unchanged. It replays the accepted
stack on fixed OHLCV snapshots and asks whether bad trades cluster when their
sector basket underperforms SPY during the trade's holding period. The output
is a taxonomy artifact plus winner-collateral estimate for future lifecycle
or ranking experiments.
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
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260426-059"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_058_sector_relative_breakdown_audit.json",
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
SECTOR_UNDERPERF_SPY_PCT = -0.02
STOCK_UNDERPERF_SECTOR_PCT = -0.02


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


def _close_by_date(rows: list[dict]) -> dict[str, float]:
    out = {}
    for row in rows:
        date = row.get("Date")
        close = row.get("Close")
        if date and isinstance(close, (int, float)) and close > 0:
            out[date] = close
    return out


def _return_between(closes: dict[str, float], start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    start_close = closes.get(start)
    end_close = closes.get(end)
    if isinstance(start_close, (int, float)) and start_close > 0 and isinstance(end_close, (int, float)):
        return (end_close / start_close) - 1.0
    return None


def _sector_members(snapshot: dict[str, list[dict]], sector: str | None) -> list[str]:
    if not sector or sector == "Unknown":
        return []
    return sorted(
        ticker for ticker in snapshot
        if SECTOR_MAP.get(ticker) == sector
    )


def _basket_return(
    snapshot: dict[str, list[dict]],
    tickers: list[str],
    start: str | None,
    end: str | None,
) -> float | None:
    returns = []
    for ticker in tickers:
        ret = _return_between(_close_by_date(snapshot.get(ticker, [])), start, end)
        if isinstance(ret, (int, float)):
            returns.append(ret)
    if not returns:
        return None
    return mean(returns)


def _round(value: float | None) -> float | None:
    return round(value, 6) if isinstance(value, (int, float)) else None


def _diagnostics(trade: dict, snapshot: dict[str, list[dict]]) -> dict:
    ticker = trade.get("ticker")
    sector = trade.get("sector")
    entry_date = trade.get("entry_date")
    exit_date = trade.get("exit_date")

    stock_return = _return_between(
        _close_by_date(snapshot.get(ticker, [])),
        entry_date,
        exit_date,
    )
    spy_return = _return_between(
        _close_by_date(snapshot.get("SPY", [])),
        entry_date,
        exit_date,
    )
    members = _sector_members(snapshot, sector)
    sector_return = _basket_return(snapshot, members, entry_date, exit_date)

    sector_vs_spy = None
    stock_vs_sector = None
    if isinstance(sector_return, (int, float)) and isinstance(spy_return, (int, float)):
        sector_vs_spy = sector_return - spy_return
    if isinstance(stock_return, (int, float)) and isinstance(sector_return, (int, float)):
        stock_vs_sector = stock_return - sector_return

    sector_breakdown = (
        isinstance(sector_vs_spy, (int, float))
        and sector_vs_spy <= SECTOR_UNDERPERF_SPY_PCT
    )
    stock_under_sector = (
        isinstance(stock_vs_sector, (int, float))
        and stock_vs_sector <= STOCK_UNDERPERF_SECTOR_PCT
    )
    is_bad = (trade.get("pnl") or 0) <= 0
    is_winner = (trade.get("pnl") or 0) > 0

    if is_bad and sector_breakdown and stock_under_sector:
        family = "bad_sector_breakdown_plus_stock_lag"
    elif is_bad and sector_breakdown:
        family = "bad_sector_breakdown_only"
    elif is_bad:
        family = "bad_without_sector_breakdown"
    elif is_winner and sector_breakdown:
        family = "winner_collateral_sector_breakdown"
    else:
        family = "winner_no_sector_breakdown"

    return {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "sector": sector,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "exit_reason": trade.get("exit_reason"),
        "pnl": trade.get("pnl"),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "stock_close_return": _round(stock_return),
        "sector_equal_weight_return": _round(sector_return),
        "spy_return": _round(spy_return),
        "sector_vs_spy": _round(sector_vs_spy),
        "stock_vs_sector": _round(stock_vs_sector),
        "sector_member_count": len(members),
        "sector_breakdown": sector_breakdown,
        "stock_under_sector": stock_under_sector,
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


def _counter(rows: list[dict], key: str) -> dict:
    return dict(sorted(Counter(row.get(key) or "unknown" for row in rows).items()))


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    result = _run_window(universe, cfg)
    snapshot = _load_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    rows = [_diagnostics(trade, snapshot) for trade in result.get("trades", [])]

    by_family = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)

    bad_sector = [
        row for row in rows
        if row["family"] in {
            "bad_sector_breakdown_only",
            "bad_sector_breakdown_plus_stock_lag",
        }
    ]
    collateral = [
        row for row in rows
        if row["family"] == "winner_collateral_sector_breakdown"
    ]

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
        "thresholds": {
            "sector_underperf_spy_pct": SECTOR_UNDERPERF_SPY_PCT,
            "stock_underperf_sector_pct": STOCK_UNDERPERF_SECTOR_PCT,
        },
        "family_counts": _counter(rows, "family"),
        "summary_by_family": {
            family: _summary(items)
            for family, items in sorted(by_family.items())
        },
        "bad_sector_strategy_counts": _counter(bad_sector, "strategy"),
        "bad_sector_sector_counts": _counter(bad_sector, "sector"),
        "collateral_strategy_counts": _counter(collateral, "strategy"),
        "collateral_sector_counts": _counter(collateral, "sector"),
        "bad_sector_rows": sorted(bad_sector, key=lambda row: row.get("pnl") or 0),
        "winner_collateral_rows": sorted(
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

    all_bad = [
        row for window in windows.values()
        for row in window["bad_sector_rows"]
    ]
    all_collateral = [
        row for window in windows.values()
        for row in window["winner_collateral_rows"]
    ]
    total_trades = sum(window["metrics"]["trade_count"] or 0 for window in windows.values())
    bad_pnl = sum(row.get("pnl") or 0.0 for row in all_bad)
    collateral_pnl = sum(row.get("pnl") or 0.0 for row in all_collateral)

    aggregate = {
        "total_trades": total_trades,
        "bad_sector_breakdown_count": len(all_bad),
        "bad_sector_breakdown_frequency": round(len(all_bad) / total_trades, 4) if total_trades else None,
        "bad_sector_breakdown_pnl_sum": round(bad_pnl, 2),
        "winner_collateral_sector_breakdown_count": len(all_collateral),
        "winner_collateral_sector_breakdown_pnl_sum": round(collateral_pnl, 2),
        "bad_sector_strategy_counts": _counter(all_bad, "strategy"),
        "bad_sector_sector_counts": _counter(all_bad, "sector"),
        "collateral_strategy_counts": _counter(all_collateral, "strategy"),
        "collateral_sector_counts": _counter(all_collateral, "sector"),
        "collateral_to_bad_count_ratio": (
            round(len(all_collateral) / len(all_bad), 4) if all_bad else None
        ),
        "collateral_to_bad_pnl_abs_ratio": (
            round(collateral_pnl / abs(bad_pnl), 4) if bad_pnl else None
        ),
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "observed_only",
        "hypothesis": (
            "Accepted-stack bad trades may contain a reproducible post-entry "
            "sector-relative breakdown family distinct from low-MFE, overnight "
            "gap-down, near-target giveback, and price-only early adverse "
            "excursion audits."
        ),
        "single_causal_variable": (
            "post-entry sector-relative breakdown taxonomy for accepted-stack trades"
        ),
        "thresholds": {
            "sector_underperf_spy_pct": SECTOR_UNDERPERF_SPY_PCT,
            "stock_underperf_sector_pct": STOCK_UNDERPERF_SECTOR_PCT,
            "sector_proxy": "equal-weight current-universe members in same sector",
            "benchmark": "SPY close-to-close return over each trade hold",
        },
        "windows": windows,
        "aggregate": aggregate,
        "interpretation": {
            "status": "observed_only",
            "production_change": "none",
            "why_not_prior_family": (
                "This taxonomy is based on post-entry sector basket deterioration "
                "relative to SPY. It does not use low-MFE, overnight gap size, "
                "target giveback, or early adverse excursion as the family trigger."
            ),
            "next_experiment_unlocked": (
                "A default-off lifecycle replay can test whether a persistent "
                "sector-underperformance state plus stock-under-sector lag should "
                "reduce risk or tighten exits, but only if winner collateral is "
                "acceptable."
            ),
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": OUT_JSON,
        "aggregate": aggregate,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
