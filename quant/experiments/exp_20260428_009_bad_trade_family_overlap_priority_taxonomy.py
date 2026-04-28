"""exp-20260428-009: bad-trade family overlap priority taxonomy.

Observed-only loss attribution. This runner changes no production behavior. It
replays the accepted stack over the fixed windows, computes post-trade audit
features, and measures which previously observed loss families explain the same
bad trades versus merely rediscovering the same collateral-prone samples.
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


EXPERIMENT_ID = "exp-20260428-009"
OUT_DIR = os.path.join(ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(
    OUT_DIR,
    "exp_20260428_009_bad_trade_family_overlap_priority_taxonomy.json",
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
                "regime": "slow-melt bull / accepted-stack dominant tape",
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
                "regime": "rotation-heavy bull where strategy makes money but lags indexes",
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
                "regime": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

FAMILY_ORDER = [
    "low_mfe_stopout",
    "overnight_gap_down_damage",
    "sector_relative_breakdown",
    "near_target_giveback",
    "wide_stop_distance",
    "strict_extension_weak_followthrough",
    "weak_followthrough_any",
]


def _pct(num: float | None, den: float | None) -> float | None:
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)) or den == 0:
        return None
    return (num / den) - 1


def _round(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if isinstance(value, (int, float)) else None


def _load_snapshot(path: str) -> dict[str, list[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["ohlcv"]


def _index_by_date(rows: list[dict]) -> dict[str, int]:
    return {row["Date"]: idx for idx, row in enumerate(rows)}


def _window_rows(rows: list[dict], start_idx: int, end_idx: int) -> list[dict]:
    lo = min(start_idx, end_idx)
    hi = max(start_idx, end_idx)
    return rows[lo : hi + 1]


def _trade_path_features(trade: dict, rows: list[dict], entry_idx: int, exit_idx: int) -> dict:
    path = _window_rows(rows, entry_idx, exit_idx)
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    if not path or not isinstance(entry, (int, float)):
        return {"path_status": "missing_path"}

    highs = [row.get("High") for row in path if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in path if isinstance(row.get("Low"), (int, float))]
    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = _pct(max_high, entry)
    mae_pct = _pct(min_low, entry)
    risk_pct = trade.get("initial_risk_pct")
    if not isinstance(risk_pct, (int, float)) and isinstance(stop, (int, float)):
        risk_pct = (entry - stop) / entry

    target_progress = None
    target_mult = trade.get("target_mult_used")
    if (
        isinstance(max_high, (int, float))
        and isinstance(stop, (int, float))
        and isinstance(target_mult, (int, float))
        and entry > stop
    ):
        target_price = entry + target_mult * (entry - stop)
        if target_price > entry:
            target_progress = (max_high - entry) / (target_price - entry)

    overnight_gaps = []
    for prev, curr in zip(path, path[1:]):
        gap = _pct(curr.get("Open"), prev.get("Close"))
        if gap is not None:
            overnight_gaps.append(gap)
    worst_gap_pct = min(overnight_gaps) if overnight_gaps else None
    worst_gap_r = (
        worst_gap_pct / risk_pct
        if isinstance(worst_gap_pct, (int, float)) and isinstance(risk_pct, (int, float)) and risk_pct
        else None
    )

    return {
        "path_status": "ok",
        "mfe_pct": _round(mfe_pct),
        "mae_pct": _round(mae_pct),
        "max_high": _round(max_high, 4),
        "min_low": _round(min_low, 4),
        "target_progress": _round(target_progress),
        "worst_overnight_gap_pct": _round(worst_gap_pct),
        "worst_overnight_gap_r": _round(worst_gap_r),
    }


def _extension_features(rows: list[dict], entry_idx: int) -> dict:
    signal_idx = entry_idx - 1
    if signal_idx < 20:
        return {"status": "insufficient_history"}
    signal = rows[signal_idx]
    close = signal.get("Close")
    prior_10 = rows[signal_idx - 10].get("Close")
    closes_10 = [row.get("Close") for row in rows[signal_idx - 9 : signal_idx + 1]]
    closes_20 = [row.get("Close") for row in rows[signal_idx - 19 : signal_idx + 1]]
    closes_10 = [v for v in closes_10 if isinstance(v, (int, float))]
    closes_20 = [v for v in closes_20 if isinstance(v, (int, float))]
    highs_20 = [row.get("High") for row in rows[signal_idx - 19 : signal_idx + 1]]
    lows_20 = [row.get("Low") for row in rows[signal_idx - 19 : signal_idx + 1]]
    highs_20 = [v for v in highs_20 if isinstance(v, (int, float))]
    lows_20 = [v for v in lows_20 if isinstance(v, (int, float))]
    sma10 = mean(closes_10) if len(closes_10) == 10 else None
    sma20 = mean(closes_20) if len(closes_20) == 20 else None
    high20 = max(highs_20) if highs_20 else None
    low20 = min(lows_20) if lows_20 else None
    range_pos_20d = (
        (close - low20) / (high20 - low20)
        if isinstance(close, (int, float)) and high20 and low20 and high20 > low20
        else None
    )
    prior_10d_return = _pct(close, prior_10)
    close_vs_sma10 = _pct(close, sma10)
    close_vs_sma20 = _pct(close, sma20)
    flags = {
        "entry_ge_12pct_prior_10d": (prior_10d_return or 0) >= 0.12,
        "entry_ge_8pct_above_sma20": (close_vs_sma20 or 0) >= 0.08,
        "entry_top_5pct_20d_and_above_sma10": (range_pos_20d or 0) >= 0.95
        and (close_vs_sma10 or 0) >= 0.04,
    }
    return {
        "status": "ok",
        "prior_10d_return": _round(prior_10d_return),
        "close_vs_sma10": _round(close_vs_sma10),
        "close_vs_sma20": _round(close_vs_sma20),
        "range_pos_20d": _round(range_pos_20d),
        "flags": flags,
        "extended_entry": any(flags.values()),
    }


def _followthrough_features(rows: list[dict], spy_rows: list[dict], entry_idx: int, entry_date: str) -> dict:
    spy_idx = _index_by_date(spy_rows).get(entry_date)
    if entry_idx + 1 >= len(rows) or spy_idx is None or spy_idx + 1 >= len(spy_rows):
        return {"status": "insufficient_forward"}
    entry = rows[entry_idx]
    next_day = rows[entry_idx + 1]
    spy_entry = spy_rows[spy_idx]
    spy_next = spy_rows[spy_idx + 1]
    entry_day_return = _pct(entry.get("Close"), entry.get("Open"))
    next_close_return = _pct(next_day.get("Close"), entry.get("Open"))
    spy_next_return = _pct(spy_next.get("Close"), spy_entry.get("Open"))
    rs_next = (
        next_close_return - spy_next_return
        if next_close_return is not None and spy_next_return is not None
        else None
    )
    flags = {
        "entry_day_red": (entry_day_return or 0) < 0,
        "next_close_below_entry_open": (next_close_return or 0) < 0,
        "next_day_rs_vs_spy_negative": (rs_next or 0) < 0,
    }
    return {
        "status": "ok",
        "entry_day_return": _round(entry_day_return),
        "next_close_return_from_entry_open": _round(next_close_return),
        "rs_vs_spy_next_close": _round(rs_next),
        "flags": flags,
        "weak_any": any(flags.values()),
        "weak_all_three": all(flags.values()),
    }


def _sector_return(
    snapshot: dict[str, list[dict]],
    universe: list[str],
    sectors: dict[str, str | None],
    sector: str | None,
    entry_date: str,
    exit_date: str,
) -> float | None:
    if not sector:
        return None
    vals = []
    for ticker in universe:
        if sectors.get(ticker) != sector:
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
        is_loss = pnl <= 0
        if entry_idx is None or exit_idx is None:
            path = {"path_status": "missing_dates"}
            extension = {"status": "missing_dates"}
            follow = {"status": "missing_dates"}
        else:
            path = _trade_path_features(trade, ticker_rows, entry_idx, exit_idx)
            extension = _extension_features(ticker_rows, entry_idx)
            follow = _followthrough_features(ticker_rows, spy_rows, entry_idx, entry_date)

        sector_ret = _sector_return(
            snapshot, universe, sectors, trade.get("sector"), entry_date, exit_date
        )
        stock_ret = _pct(trade.get("exit_raw_price") or trade.get("exit_price"), trade.get("entry_price"))
        spy_ret = None
        if entry_date in spy_idx and exit_date in spy_idx:
            spy_ret = _pct(spy_rows[spy_idx[exit_date]].get("Close"), spy_rows[spy_idx[entry_date]].get("Open"))
        stock_vs_sector = (
            stock_ret - sector_ret
            if stock_ret is not None and sector_ret is not None
            else None
        )
        sector_vs_spy = (
            sector_ret - spy_ret
            if sector_ret is not None and spy_ret is not None
            else None
        )

        flags = {
            "low_mfe_stopout": trade.get("exit_reason") == "stop"
            and (path.get("mfe_pct") or 0) < 0.01,
            "overnight_gap_down_damage": (path.get("worst_overnight_gap_pct") or 0) <= -0.02
            or (path.get("worst_overnight_gap_r") or 0) <= -0.5,
            "sector_relative_breakdown": (sector_vs_spy or 0) <= -0.02
            and (stock_vs_sector or 0) <= -0.02,
            "near_target_giveback": (path.get("target_progress") or 0) >= 0.75
            and trade.get("exit_reason") != "target",
            "wide_stop_distance": (trade.get("initial_risk_pct") or 0) >= 0.05,
            "strict_extension_weak_followthrough": bool(extension.get("extended_entry"))
            and bool(follow.get("weak_all_three")),
            "weak_followthrough_any": bool(extension.get("extended_entry"))
            and bool(follow.get("weak_any")),
        }
        primary = next((family for family in FAMILY_ORDER if flags.get(family)), "unclassified")
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
                "is_loss": is_loss,
                "primary_family": primary if is_loss else None,
                "family_flags": flags,
                "audit_features": {
                    "path": path,
                    "extension": extension,
                    "followthrough": follow,
                    "sector_return": _round(sector_ret),
                    "stock_return_raw": _round(stock_ret),
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


def _family_stats(all_rows: list[dict]) -> dict:
    losses = [row for row in all_rows if row["is_loss"]]
    wins = [row for row in all_rows if not row["is_loss"]]
    total_loss_abs = sum(abs(row["pnl"]) for row in losses)
    sorted_losses = sorted(losses, key=lambda row: row["pnl"])
    tail_cutoff = max(1, round(len(sorted_losses) * 0.25)) if sorted_losses else 0
    tail_losses = sorted_losses[:tail_cutoff]
    tail_ids = {
        (row["window"], row["ticker"], row["entry_date"], row["exit_date"])
        for row in tail_losses
    }
    stats = OrderedDict()
    for family in FAMILY_ORDER:
        loss_hits = [row for row in losses if row["family_flags"].get(family)]
        win_hits = [row for row in wins if row["family_flags"].get(family)]
        loss_abs = sum(abs(row["pnl"]) for row in loss_hits)
        win_pnl = sum(row["pnl"] for row in win_hits)
        tail_hit_abs = sum(
            abs(row["pnl"])
            for row in loss_hits
            if (row["window"], row["ticker"], row["entry_date"], row["exit_date"]) in tail_ids
        )
        stats[family] = {
            "loss_count": len(loss_hits),
            "loss_pnl_abs": round(loss_abs, 2),
            "loss_dollar_share": round(loss_abs / total_loss_abs, 4) if total_loss_abs else None,
            "tail_loss_pnl_abs": round(tail_hit_abs, 2),
            "tail_loss_share": round(tail_hit_abs / loss_abs, 4) if loss_abs else None,
            "winner_collateral_count": len(win_hits),
            "winner_collateral_pnl": round(win_pnl, 2),
            "naive_avoid_loss_minus_collateral": round(loss_abs - win_pnl, 2),
            "loss_summary": _summary(loss_hits),
            "winner_collateral_summary": _summary(win_hits),
        }
    return stats


def _overlap_matrix(rows: list[dict]) -> dict:
    losses = [row for row in rows if row["is_loss"]]
    matrix = OrderedDict()
    for a in FAMILY_ORDER:
        matrix[a] = OrderedDict()
        for b in FAMILY_ORDER:
            matrix[a][b] = sum(
                1 for row in losses if row["family_flags"].get(a) and row["family_flags"].get(b)
            )
    return matrix


def main() -> int:
    universe = get_universe()
    windows = OrderedDict()
    all_rows = []
    for label, cfg in WINDOWS.items():
        payload = _run_window(label, cfg, universe)
        windows[label] = {
            "range": {"start": cfg["start"], "end": cfg["end"]},
            "regime": cfg["regime"],
            "metrics": payload["metrics"],
            "trade_count": len(payload["rows"]),
        }
        all_rows.extend(payload["rows"])

    losses = [row for row in all_rows if row["is_loss"]]
    wins = [row for row in all_rows if not row["is_loss"]]
    primary_counts = Counter(row["primary_family"] for row in losses)
    primary_loss_abs = Counter()
    for row in losses:
        primary_loss_abs[row["primary_family"]] += abs(row["pnl"])

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "bad-trade family overlap priority taxonomy",
        "strategy_behavior_changed": False,
        "history_guardrails": {
            "does_not_add_filter": True,
            "does_not_promote_weak_followthrough_exit": True,
            "does_not_repeat_low_mfe_exit_replay": True,
            "does_not_touch_production_strategy": True,
        },
        "family_definitions": {
            "low_mfe_stopout": "stop exit with max favorable excursion below +1%",
            "overnight_gap_down_damage": "worst post-entry overnight gap <= -2% or <= -0.5R",
            "sector_relative_breakdown": "same-sector proxy underperforms SPY by >=2pp and stock underperforms sector by >=2pp over holding period",
            "near_target_giveback": "reached at least 75% of modeled target distance but did not exit by target",
            "wide_stop_distance": "initial risk distance >=5% of entry",
            "strict_extension_weak_followthrough": "extended entry plus all three weak follow-through flags from rejected exp-20260428-007",
            "weak_followthrough_any": "extended entry plus any weak follow-through flag; included only as collateral warning",
        },
        "windows": windows,
        "aggregate": {
            "trade_count": len(all_rows),
            "loss_count": len(losses),
            "win_count": len(wins),
            "loss_pnl_abs": round(sum(abs(row["pnl"]) for row in losses), 2),
            "winner_pnl": round(sum(row["pnl"] for row in wins), 2),
            "unclassified_loss_count": primary_counts.get("unclassified", 0),
            "unclassified_loss_pnl_abs": round(primary_loss_abs.get("unclassified", 0.0), 2),
            "primary_family_counts": dict(primary_counts),
            "primary_family_loss_pnl_abs": {
                family: round(value, 2) for family, value in primary_loss_abs.items()
            },
        },
        "family_stats": _family_stats(all_rows),
        "loss_overlap_matrix": _overlap_matrix(all_rows),
        "loss_rows": losses,
        "winner_collateral_rows": [
            row
            for row in wins
            if any(row["family_flags"].get(family) for family in FAMILY_ORDER)
        ],
        "interpretation": {
            "status": "observed_only",
            "primary_use": "Use this as a map for future alpha experiments; do not convert any single family into a filter without separate replay.",
            "mechanism_warning": "The weak-followthrough flags are intentionally reported with collateral because nearby OHLCV-only exit variants were rejected.",
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)

    print(json.dumps(artifact["aggregate"], indent=2))
    print("Top family stats:")
    for family, stats in artifact["family_stats"].items():
        if stats["loss_count"] or stats["winner_collateral_count"]:
            print(
                family,
                "losses=",
                stats["loss_count"],
                "loss_abs=",
                stats["loss_pnl_abs"],
                "collateral=",
                stats["winner_collateral_count"],
                "collateral_pnl=",
                stats["winner_collateral_pnl"],
            )
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
