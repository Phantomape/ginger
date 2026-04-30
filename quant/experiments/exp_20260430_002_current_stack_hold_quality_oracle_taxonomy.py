"""exp-20260430-002: current-stack hold-quality oracle taxonomy.

Observed-only loss attribution. This runner changes no production behavior.
It replays the accepted stack over fixed windows, classifies losing trades by
post-entry hold quality, and estimates both oracle loss dollars and winner
collateral before any future alpha/risk experiment is attempted.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from statistics import mean


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
QUANT_DIR = os.path.join(ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260430-010"
OUT_DIR = os.path.join(ROOT, "data", "experiments", "exp-20260430-002")
OUT_JSON = os.path.join(
    OUT_DIR,
    "exp_20260430_002_current_stack_hold_quality_oracle_taxonomy.json",
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": os.path.join(
                    ROOT, "data", "ohlcv_snapshot_20251023_20260421.json"
                ),
                "regime": "accepted-stack strong tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": os.path.join(
                    ROOT, "data", "ohlcv_snapshot_20250423_20251022.json"
                ),
                "regime": "profitable but benchmark-lagging rotation tape",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": os.path.join(
                    ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"
                ),
                "regime": "older mixed tape with lower win rate",
            },
        ),
    ]
)

FAMILY_ORDER = [
    "low_mfe_stopout",
    "failed_followthrough",
    "overnight_gap_damage",
    "sector_relative_breakdown",
    "giveback_after_mfe",
    "wide_stop_distance",
]


def _pct(num: float | None, den: float | None) -> float | None:
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)) or den == 0:
        return None
    return (num / den) - 1


def _round(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if isinstance(value, (int, float)) else None


def _load_snapshot(path: str) -> dict[str, list[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["ohlcv"]


def _index_by_date(rows: list[dict]) -> dict[str, int]:
    return {row["Date"]: idx for idx, row in enumerate(rows)}


def _trade_path(rows: list[dict], entry_idx: int, exit_idx: int) -> list[dict]:
    lo = min(entry_idx, exit_idx)
    hi = max(entry_idx, exit_idx)
    return rows[lo : hi + 1]


def _path_features(trade: dict, rows: list[dict], entry_idx: int, exit_idx: int) -> dict:
    path = _trade_path(rows, entry_idx, exit_idx)
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    if not path or not isinstance(entry, (int, float)):
        return {"status": "missing_path"}

    highs = [row.get("High") for row in path if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in path if isinstance(row.get("Low"), (int, float))]
    closes = [row.get("Close") for row in path if isinstance(row.get("Close"), (int, float))]
    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = _pct(max_high, entry)
    mae_pct = _pct(min_low, entry)
    close_return = _pct(closes[-1], entry) if closes else None

    risk_pct = trade.get("initial_risk_pct")
    if not isinstance(risk_pct, (int, float)) and isinstance(stop, (int, float)):
        risk_pct = (entry - stop) / entry

    gaps = []
    for prev, curr in zip(path, path[1:]):
        gap = _pct(curr.get("Open"), prev.get("Close"))
        if gap is not None:
            gaps.append(gap)
    worst_gap = min(gaps) if gaps else None
    worst_gap_r = (
        worst_gap / risk_pct
        if isinstance(worst_gap, (int, float)) and isinstance(risk_pct, (int, float)) and risk_pct
        else None
    )
    return {
        "status": "ok",
        "mfe_pct": _round(mfe_pct),
        "mae_pct": _round(mae_pct),
        "close_return": _round(close_return),
        "worst_gap_pct": _round(worst_gap),
        "worst_gap_r": _round(worst_gap_r),
    }


def _followthrough(rows: list[dict], spy_rows: list[dict], entry_idx: int, entry_date: str) -> dict:
    spy_idx = _index_by_date(spy_rows).get(entry_date)
    if entry_idx + 1 >= len(rows) or spy_idx is None or spy_idx + 1 >= len(spy_rows):
        return {"status": "insufficient_forward"}
    entry = rows[entry_idx]
    next_day = rows[entry_idx + 1]
    spy_entry = spy_rows[spy_idx]
    spy_next = spy_rows[spy_idx + 1]
    entry_day_return = _pct(entry.get("Close"), entry.get("Open"))
    next_return = _pct(next_day.get("Close"), entry.get("Open"))
    spy_next_return = _pct(spy_next.get("Close"), spy_entry.get("Open"))
    rs_next = next_return - spy_next_return if next_return is not None and spy_next_return is not None else None
    flags = {
        "entry_day_red": (entry_day_return or 0) < 0,
        "next_close_below_entry_open": (next_return or 0) < 0,
        "next_day_rs_vs_spy_negative": (rs_next or 0) < 0,
    }
    return {
        "status": "ok",
        "entry_day_return": _round(entry_day_return),
        "next_close_return": _round(next_return),
        "rs_vs_spy_next_close": _round(rs_next),
        "weak_count": sum(1 for v in flags.values() if v),
        "flags": flags,
    }


def _sector_return(snapshot: dict[str, list[dict]], sectors: dict[str, str | None], sector: str | None, entry_date: str, exit_date: str) -> float | None:
    if not sector:
        return None
    vals = []
    for ticker, ticker_sector in sectors.items():
        if ticker_sector != sector:
            continue
        rows = snapshot.get(ticker) or []
        idx = _index_by_date(rows)
        start = idx.get(entry_date)
        end = idx.get(exit_date)
        if start is None or end is None:
            continue
        ret = _pct(rows[end].get("Close"), rows[start].get("Open"))
        if ret is not None:
            vals.append(ret)
    return mean(vals) if vals else None


def _classify(trade: dict, path: dict, follow: dict, stock_vs_sector: float | None, sector_vs_spy: float | None) -> dict[str, bool]:
    return {
        "low_mfe_stopout": trade.get("exit_reason") == "stop" and (path.get("mfe_pct") or 0) < 0.01,
        "failed_followthrough": follow.get("weak_count", 0) >= 2 and (path.get("mfe_pct") or 0) < 0.03,
        "overnight_gap_damage": (path.get("worst_gap_pct") or 0) <= -0.02 or (path.get("worst_gap_r") or 0) <= -0.5,
        "sector_relative_breakdown": (stock_vs_sector or 0) <= -0.02 and (sector_vs_spy or 0) <= -0.02,
        "giveback_after_mfe": (path.get("mfe_pct") or 0) >= 0.05 and trade.get("exit_reason") != "target" and (trade.get("pnl") or 0) <= 0,
        "wide_stop_distance": (trade.get("initial_risk_pct") or 0) >= 0.05,
    }


def _run_window(label: str, cfg: dict, universe: list[str]) -> dict:
    engine = BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        ohlcv_snapshot_path=cfg["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label}: {result['error']}")

    snapshot = _load_snapshot(cfg["snapshot"])
    spy_rows = snapshot.get("SPY") or []
    spy_idx = _index_by_date(spy_rows)
    sectors = {trade.get("ticker"): trade.get("sector") for trade in result.get("trades", [])}
    rows = []

    for trade in result.get("trades", []):
        ticker = trade.get("ticker")
        ticker_rows = snapshot.get(ticker) or []
        t_idx = _index_by_date(ticker_rows)
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        entry_idx = t_idx.get(entry_date)
        exit_idx = t_idx.get(exit_date)
        pnl = float(trade.get("pnl") or 0.0)
        if entry_idx is None or exit_idx is None:
            path = {"status": "missing_dates"}
            follow = {"status": "missing_dates"}
        else:
            path = _path_features(trade, ticker_rows, entry_idx, exit_idx)
            follow = _followthrough(ticker_rows, spy_rows, entry_idx, entry_date)

        stock_ret = _pct(trade.get("exit_raw_price") or trade.get("exit_price"), trade.get("entry_price"))
        sector_ret = _sector_return(snapshot, sectors, trade.get("sector"), entry_date, exit_date)
        spy_ret = None
        if entry_date in spy_idx and exit_date in spy_idx:
            spy_ret = _pct(spy_rows[spy_idx[exit_date]].get("Close"), spy_rows[spy_idx[entry_date]].get("Open"))
        stock_vs_sector = stock_ret - sector_ret if stock_ret is not None and sector_ret is not None else None
        sector_vs_spy = sector_ret - spy_ret if sector_ret is not None and spy_ret is not None else None
        flags = _classify(trade, path, follow, stock_vs_sector, sector_vs_spy)
        primary = next((name for name in FAMILY_ORDER if flags[name]), "unclassified")
        rows.append(
            {
                "window": label,
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": entry_date,
                "exit_date": exit_date,
                "exit_reason": trade.get("exit_reason"),
                "pnl": round(pnl, 2),
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "is_loss": pnl <= 0,
                "primary_family": primary if pnl <= 0 else None,
                "family_flags": flags,
                "features": {
                    "path": path,
                    "followthrough": follow,
                    "stock_return": _round(stock_ret),
                    "sector_return": _round(sector_ret),
                    "spy_return": _round(spy_ret),
                    "stock_vs_sector": _round(stock_vs_sector),
                    "sector_vs_spy": _round(sector_vs_spy),
                },
            }
        )

    return {
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_pnl": result.get("total_pnl"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "win_rate": result.get("win_rate"),
            "trade_count": result.get("total_trades"),
            "survival_rate": result.get("survival_rate"),
        },
        "rows": rows,
    }


def _summary(rows: list[dict]) -> dict:
    pnl = [row["pnl"] for row in rows]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnl), 2),
        "avg_pnl": round(mean(pnl), 2) if pnl else None,
        "window_counts": dict(sorted(Counter(row["window"] for row in rows).items())),
        "strategy_counts": dict(sorted(Counter(row["strategy"] for row in rows).items())),
        "sector_counts": dict(sorted(Counter(row["sector"] for row in rows).items())),
        "tickers": sorted({row["ticker"] for row in rows}),
    }


def _family_stats(rows: list[dict]) -> OrderedDict:
    losses = [row for row in rows if row["is_loss"]]
    wins = [row for row in rows if not row["is_loss"]]
    total_loss = sum(abs(row["pnl"]) for row in losses)
    tail_n = max(1, round(len(losses) * 0.25)) if losses else 0
    tail_ids = {
        (row["window"], row["ticker"], row["entry_date"], row["exit_date"])
        for row in sorted(losses, key=lambda row: row["pnl"])[:tail_n]
    }
    stats = OrderedDict()
    for family in FAMILY_ORDER:
        loss_hits = [row for row in losses if row["family_flags"][family]]
        win_hits = [row for row in wins if row["family_flags"][family]]
        loss_abs = sum(abs(row["pnl"]) for row in loss_hits)
        win_pnl = sum(row["pnl"] for row in win_hits)
        tail_abs = sum(
            abs(row["pnl"])
            for row in loss_hits
            if (row["window"], row["ticker"], row["entry_date"], row["exit_date"]) in tail_ids
        )
        stats[family] = {
            "loss_count": len(loss_hits),
            "loss_pnl_abs": round(loss_abs, 2),
            "loss_dollar_share": round(loss_abs / total_loss, 4) if total_loss else None,
            "tail_loss_pnl_abs": round(tail_abs, 2),
            "tail_loss_share_of_family": round(tail_abs / loss_abs, 4) if loss_abs else None,
            "winner_collateral_count": len(win_hits),
            "winner_collateral_pnl": round(win_pnl, 2),
            "collateral_to_loss_abs": round(win_pnl / loss_abs, 4) if loss_abs else None,
            "oracle_loss_if_perfectly_avoided": round(loss_abs, 2),
            "naive_filter_net_after_collateral": round(loss_abs - win_pnl, 2),
            "loss_summary": _summary(loss_hits),
            "winner_collateral_summary": _summary(win_hits),
        }
    return stats


def _future_candidates(stats: OrderedDict) -> list[dict]:
    candidates = []
    for family, row in stats.items():
        windows = len(row["loss_summary"]["window_counts"])
        if row["loss_count"] >= 3 and windows >= 2 and (row["collateral_to_loss_abs"] is None or row["collateral_to_loss_abs"] < 1.0):
            candidates.append(
                {
                    "candidate": family,
                    "why": "Repeated across windows with limited observed winner collateral.",
                    "not_a_rule_yet": True,
                    "next_test_shape": "shadow replay with an orthogonal event/state discriminator, not a direct filter",
                    "loss_count": row["loss_count"],
                    "loss_pnl_abs": row["loss_pnl_abs"],
                    "winner_collateral_count": row["winner_collateral_count"],
                    "winner_collateral_pnl": row["winner_collateral_pnl"],
                }
            )
    return candidates


def main() -> int:
    universe = get_universe()
    windows = OrderedDict()
    all_rows = []
    for label, cfg in WINDOWS.items():
        result = _run_window(label, cfg, universe)
        windows[label] = {
            "range": {"start": cfg["start"], "end": cfg["end"]},
            "regime": cfg["regime"],
            "metrics": result["metrics"],
            "trade_count": len(result["rows"]),
        }
        all_rows.extend(result["rows"])

    losses = [row for row in all_rows if row["is_loss"]]
    wins = [row for row in all_rows if not row["is_loss"]]
    primary_counts = Counter(row["primary_family"] for row in losses)
    primary_loss_abs = Counter()
    for row in losses:
        primary_loss_abs[row["primary_family"]] += abs(row["pnl"])

    stats = _family_stats(all_rows)
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "current-stack hold-quality oracle taxonomy",
        "strategy_behavior_changed": False,
        "history_guardrails": {
            "does_not_add_filter": True,
            "does_not_modify_production_strategy": True,
            "does_not_treat_1_to_3_trades_as_rule": True,
            "checks_winner_collateral": True,
        },
        "family_definitions": {
            "low_mfe_stopout": "stop exit with max favorable excursion below +1%",
            "failed_followthrough": "at least two day-0/day-1 weak follow-through flags and MFE below +3%",
            "overnight_gap_damage": "worst post-entry overnight gap <= -2% or <= -0.5R",
            "sector_relative_breakdown": "stock underperformed sector by >=2pp while sector underperformed SPY by >=2pp",
            "giveback_after_mfe": "losing non-target trade after reaching at least +5% MFE",
            "wide_stop_distance": "initial stop distance >=5% of entry",
        },
        "windows": windows,
        "aggregate": {
            "trade_count": len(all_rows),
            "loss_count": len(losses),
            "win_count": len(wins),
            "loss_pnl_abs": round(sum(abs(row["pnl"]) for row in losses), 2),
            "winner_pnl": round(sum(row["pnl"] for row in wins), 2),
            "primary_family_counts": dict(primary_counts),
            "primary_family_loss_pnl_abs": {
                family: round(value, 2) for family, value in primary_loss_abs.items()
            },
        },
        "family_stats": stats,
        "future_test_candidates": _future_candidates(stats),
        "loss_rows": losses,
        "winner_collateral_rows": [
            row for row in wins if any(row["family_flags"][family] for family in FAMILY_ORDER)
        ],
        "interpretation": {
            "status": "observed_only",
            "oracle_note": "Oracle dollars are an upper bound: they assume perfect identification before the exit path is known.",
            "llm_news_context": "This audit did not use LLM/news context; future tests should only add it as an orthogonal event/state discriminator.",
            "do_not_promote_directly": "No family here should be converted directly into a filter without a separate replay and collateral check.",
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)

    print(json.dumps(artifact["aggregate"], indent=2, ensure_ascii=False))
    for item in artifact["future_test_candidates"]:
        print("candidate", json.dumps(item, ensure_ascii=False))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
