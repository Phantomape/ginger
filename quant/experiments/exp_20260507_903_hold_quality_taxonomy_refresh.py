"""exp-20260507-903: refreshed hold-quality loss taxonomy.

Observed-only loss attribution. This runner changes no production behavior and
does not add filters. It replays the accepted stack over the three canonical
snapshot windows, classifies bad trades by post-entry hold quality, and records
winner collateral plus semantic-context coverage for future alpha tests.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from statistics import mean, median


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
QUANT_DIR = os.path.join(ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-903"
OUT_DIR = os.path.join(ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(OUT_DIR, "exp_20260507_903_hold_quality_taxonomy_refresh.json")

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20251023_20260421.json"),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20250423_20251022.json"),
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

FAMILIES = OrderedDict(
    [
        ("low_mfe_stopout", "Stop exit with MFE below +1%."),
        (
            "failed_early_followthrough",
            "Entry path has negative day-2 return and underperforms SPY by day 2.",
        ),
        (
            "moderate_mfe_full_reversal",
            "Stop/loss after at least +1% MFE but less than 50% target progress.",
        ),
        (
            "overnight_or_open_damage",
            "Post-entry overnight gap/open damage <= -1.25% or <= -0.4R.",
        ),
        (
            "sector_relative_breakdown",
            "Stock trails sector by >=2pp while sector trails SPY by >=2pp.",
        ),
        (
            "exit_failure_after_mfe",
            "Non-target loser after reaching at least +3% MFE.",
        ),
        (
            "same_entry_date_loss_cluster",
            "Entry date has at least two accepted-stack losses.",
        ),
    ]
)


def _round(value, ndigits=6):
    return round(float(value), ndigits) if isinstance(value, (int, float)) else None


def _pct(num, den):
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)) or den == 0:
        return None
    return float(num) / float(den) - 1.0


def _yyyymmdd(date_text):
    return str(date_text or "").replace("-", "")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_snapshot(path):
    return _load_json(path, {}).get("ohlcv", {})


def _index_by_date(rows):
    return {row["Date"]: idx for idx, row in enumerate(rows)}


def _safe_mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return mean(vals) if vals else None


def _safe_median(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return median(vals) if vals else None


def _path_features(trade, rows, entry_idx, exit_idx):
    path = rows[min(entry_idx, exit_idx) : max(entry_idx, exit_idx) + 1]
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    risk_pct = trade.get("initial_risk_pct")
    if not isinstance(risk_pct, (int, float)) and isinstance(entry, (int, float)) and isinstance(stop, (int, float)):
        risk_pct = (entry - stop) / entry
    if not path or not isinstance(entry, (int, float)):
        return {"path_status": "missing"}

    highs = [row.get("High") for row in path if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in path if isinstance(row.get("Low"), (int, float))]
    closes = [row.get("Close") for row in path if isinstance(row.get("Close"), (int, float))]
    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = _pct(max_high, entry)
    mae_pct = _pct(min_low, entry)
    mfe_r = mfe_pct / risk_pct if isinstance(mfe_pct, (int, float)) and risk_pct else None
    mae_r = mae_pct / risk_pct if isinstance(mae_pct, (int, float)) and risk_pct else None

    target_progress = None
    target_mult = trade.get("target_mult_used")
    if isinstance(stop, (int, float)) and isinstance(target_mult, (int, float)) and entry > stop:
        target = entry + target_mult * (entry - stop)
        target_progress = (max_high - entry) / (target - entry) if isinstance(max_high, (int, float)) and target > entry else None

    overnight_gaps = []
    open_vs_entry = []
    for prev, curr in zip(path, path[1:]):
        gap = _pct(curr.get("Open"), prev.get("Close"))
        if gap is not None:
            overnight_gaps.append(gap)
        oe = _pct(curr.get("Open"), entry)
        if oe is not None:
            open_vs_entry.append(oe)

    return {
        "path_status": "ok",
        "hold_bars": len(path) - 1,
        "mfe_pct": _round(mfe_pct),
        "mae_pct": _round(mae_pct),
        "mfe_r": _round(mfe_r),
        "mae_r": _round(mae_r),
        "target_progress": _round(target_progress),
        "worst_overnight_gap_pct": _round(min(overnight_gaps) if overnight_gaps else None),
        "worst_open_vs_entry_pct": _round(min(open_vs_entry) if open_vs_entry else None),
        "close_below_entry_share": _round(sum(1 for c in closes if c < entry) / len(closes) if closes else None),
    }


def _forward_features(rows, spy_rows, entry_idx, entry_date):
    spy_idx = _index_by_date(spy_rows).get(entry_date)
    if entry_idx is None or spy_idx is None or entry_idx + 2 >= len(rows) or spy_idx + 2 >= len(spy_rows):
        return {"forward_status": "insufficient_forward"}
    entry_open = rows[entry_idx].get("Open")
    spy_open = spy_rows[spy_idx].get("Open")
    d2_ret = _pct(rows[entry_idx + 2].get("Close"), entry_open)
    spy_d2_ret = _pct(spy_rows[spy_idx + 2].get("Close"), spy_open)
    return {
        "forward_status": "ok",
        "d2_return_from_entry_open": _round(d2_ret),
        "d2_excess_vs_spy": _round(d2_ret - spy_d2_ret if d2_ret is not None and spy_d2_ret is not None else None),
        "d2_close_below_entry_open": bool(isinstance(d2_ret, (int, float)) and d2_ret < 0),
        "d2_underperformed_spy": bool(isinstance(d2_ret, (int, float)) and isinstance(spy_d2_ret, (int, float)) and d2_ret < spy_d2_ret),
    }


def _sector_return(snapshot, sector_by_ticker, sector, entry_date, exit_date):
    vals = []
    if not sector:
        return None
    for ticker, ticker_sector in sector_by_ticker.items():
        if ticker_sector != sector:
            continue
        rows = snapshot.get(ticker) or []
        idx = _index_by_date(rows)
        si, ei = idx.get(entry_date), idx.get(exit_date)
        if si is None or ei is None:
            continue
        ret = _pct(rows[ei].get("Close"), rows[si].get("Open"))
        if ret is not None:
            vals.append(ret)
    return mean(vals) if vals else None


def _news_hits(date_key, ticker):
    hits = []
    for prefix in ("clean_news", "clean_trade_news"):
        path = os.path.join(ROOT, "data", f"{prefix}_{date_key}.json")
        for item in _load_json(path, []):
            if ticker in (item.get("tickers") or []):
                hits.append(
                    {
                        "source_file": os.path.basename(path),
                        "tier": item.get("tier"),
                        "title": item.get("title"),
                    }
                )
    return hits


def _semantic_context(entry_date, ticker, strategy):
    date_key = _yyyymmdd(entry_date)
    earnings = _load_json(os.path.join(ROOT, "data", f"earnings_snapshot_{date_key}.json"), {})
    event_snapshot = _load_json(os.path.join(ROOT, "data", f"event_snapshot_{date_key}.json"), {})
    events = (event_snapshot.get("events_by_ticker") or {}).get(ticker) or []
    news = _news_hits(date_key, ticker)
    llm_files = [
        name
        for name in (
            f"llm_prompt_resp_{date_key}.json",
            f"llm_output_{date_key}.json",
            f"llm_decision_{date_key}.json",
        )
        if os.path.exists(os.path.join(ROOT, "data", name))
    ]
    earnings_row = (earnings.get("earnings") or {}).get(ticker)
    return {
        "news_item_count": len(news),
        "news_tiers": sorted({hit.get("tier") or "unknown" for hit in news}),
        "news_titles_sample": [hit["title"] for hit in news[:3]],
        "llm_archive_files": llm_files,
        "llm_archive_available": bool(llm_files),
        "earnings_snapshot_available": bool(earnings_row),
        "earnings_context": earnings_row,
        "event_snapshot_count": len(events),
        "event_types": sorted({event.get("event_type") for event in events if event.get("event_type")}),
        "is_earnings_strategy": strategy == "earnings_event_long",
    }


def _classify(row, clustered_loss_dates):
    risk = float(row.get("initial_risk_pct") or 0.0)
    worst_gap = row.get("worst_overnight_gap_pct")
    worst_open = row.get("worst_open_vs_entry_pct")
    worst_gap_r = worst_gap / risk if isinstance(worst_gap, (int, float)) and risk else None
    stock_vs_sector = row.get("stock_vs_sector_return")
    sector_vs_spy = row.get("sector_vs_spy_return")
    flags = {
        "low_mfe_stopout": row.get("exit_reason") == "stop" and isinstance(row.get("mfe_pct"), (int, float)) and row["mfe_pct"] < 0.01,
        "failed_early_followthrough": bool(row.get("d2_close_below_entry_open") and row.get("d2_underperformed_spy")),
        "moderate_mfe_full_reversal": row.get("exit_reason") == "stop"
        and isinstance(row.get("mfe_pct"), (int, float))
        and row["mfe_pct"] >= 0.01
        and (row.get("target_progress") is None or row.get("target_progress") < 0.5),
        "overnight_or_open_damage": (
            (isinstance(worst_gap, (int, float)) and worst_gap <= -0.0125)
            or (isinstance(worst_open, (int, float)) and worst_open <= -0.0125)
            or (isinstance(worst_gap_r, (int, float)) and worst_gap_r <= -0.4)
        ),
        "sector_relative_breakdown": isinstance(stock_vs_sector, (int, float))
        and isinstance(sector_vs_spy, (int, float))
        and stock_vs_sector <= -0.02
        and sector_vs_spy <= -0.02,
        "exit_failure_after_mfe": row.get("exit_reason") != "target"
        and float(row.get("pnl") or 0.0) < 0
        and isinstance(row.get("mfe_pct"), (int, float))
        and row["mfe_pct"] >= 0.03,
        "same_entry_date_loss_cluster": row.get("entry_date") in clustered_loss_dates,
    }
    return flags


def _summary(rows):
    pnl = [float(row.get("pnl") or 0.0) for row in rows]
    return {
        "count": len(rows),
        "pnl_sum": _round(sum(pnl), 2),
        "avg_pnl": _round(mean(pnl), 2) if pnl else None,
        "median_pnl": _round(_safe_median(pnl), 2),
        "window_counts": dict(Counter(row.get("window") for row in rows)),
        "strategy_counts": dict(Counter(row.get("strategy") for row in rows)),
        "sector_counts": dict(Counter(row.get("sector") for row in rows)),
        "ticker_counts": dict(Counter(row.get("ticker") for row in rows)),
    }


def _family_stats(all_rows, loss_rows):
    total_loss_abs = -sum(float(row.get("pnl") or 0.0) for row in loss_rows)
    losses_sorted = sorted(loss_rows, key=lambda row: float(row.get("pnl") or 0.0))
    tail_n = max(1, round(len(losses_sorted) * 0.25)) if losses_sorted else 0
    tail_keys = {row["trade_key"] for row in losses_sorted[:tail_n]}
    stats = OrderedDict()
    for family, definition in FAMILIES.items():
        touched = [row for row in all_rows if row["family_flags"].get(family)]
        losses = [row for row in loss_rows if row["family_flags"].get(family)]
        winners = [row for row in touched if float(row.get("pnl") or 0.0) > 0]
        loss_abs = -sum(float(row.get("pnl") or 0.0) for row in losses)
        winner_pnl = sum(float(row.get("pnl") or 0.0) for row in winners)
        tail_loss_abs = -sum(float(row.get("pnl") or 0.0) for row in losses if row["trade_key"] in tail_keys)
        stats[family] = {
            "definition": definition,
            "all_trade_hit_count": len(touched),
            "loss_count": len(losses),
            "loss_pnl_abs": _round(loss_abs, 2),
            "loss_share_of_all_loss_pnl": _round(loss_abs / total_loss_abs if total_loss_abs else None),
            "tail_loss_pnl_abs": _round(tail_loss_abs, 2),
            "tail_loss_share_of_family_loss": _round(tail_loss_abs / loss_abs if loss_abs else None),
            "winner_collateral_count": len(winners),
            "winner_collateral_pnl": _round(winner_pnl, 2),
            "collateral_to_loss_abs": _round(winner_pnl / loss_abs if loss_abs else None),
            "naive_filter_net_after_collateral": _round(loss_abs - winner_pnl, 2) if loss_abs else None,
            "loss_summary": _summary(losses),
            "winner_collateral_summary": _summary(winners),
            "sample_losses": [
                {
                    "window": row["window"],
                    "ticker": row["ticker"],
                    "strategy": row["strategy"],
                    "entry_date": row["entry_date"],
                    "exit_date": row["exit_date"],
                    "pnl": _round(row["pnl"], 2),
                    "mfe_pct": row.get("mfe_pct"),
                    "d2_excess_vs_spy": row.get("d2_excess_vs_spy"),
                    "semantic_context_summary": row.get("semantic_context_summary"),
                }
                for row in losses[:10]
            ],
        }
    return stats


def _run_window(label, cfg, universe):
    engine = BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=cfg["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label}: {result['error']}")

    snapshot = _load_snapshot(cfg["snapshot"])
    spy_rows = snapshot.get("SPY") or []
    spy_idx = _index_by_date(spy_rows)
    sector_by_ticker = {trade.get("ticker"): trade.get("sector") for trade in result.get("trades", [])}
    rows = []
    for trade in result.get("trades", []):
        ticker = trade.get("ticker")
        ticker_rows = snapshot.get(ticker) or []
        idx = _index_by_date(ticker_rows)
        entry_idx = idx.get(trade.get("entry_date"))
        exit_idx = idx.get(trade.get("exit_date"))
        row = dict(trade)
        row["window"] = label
        row["window_state_note"] = cfg["state_note"]
        if entry_idx is not None and exit_idx is not None:
            row.update(_path_features(trade, ticker_rows, entry_idx, exit_idx))
            row.update(_forward_features(ticker_rows, spy_rows, entry_idx, trade.get("entry_date")))
        else:
            row.update({"path_status": "missing_dates", "forward_status": "missing_dates"})

        sector_ret = _sector_return(snapshot, sector_by_ticker, trade.get("sector"), trade.get("entry_date"), trade.get("exit_date"))
        spy_ret = None
        if trade.get("entry_date") in spy_idx and trade.get("exit_date") in spy_idx:
            spy_ret = _pct(spy_rows[spy_idx[trade["exit_date"]]].get("Close"), spy_rows[spy_idx[trade["entry_date"]]].get("Open"))
        stock_ret = _pct(trade.get("exit_raw_price") or trade.get("exit_price"), trade.get("entry_price"))
        row["stock_return_entry_to_exit"] = _round(stock_ret)
        row["sector_return_entry_to_exit"] = _round(sector_ret)
        row["spy_return_entry_to_exit"] = _round(spy_ret)
        row["stock_vs_sector_return"] = _round(stock_ret - sector_ret if stock_ret is not None and sector_ret is not None else None)
        row["sector_vs_spy_return"] = _round(sector_ret - spy_ret if sector_ret is not None and spy_ret is not None else None)
        row["is_loss"] = float(row.get("pnl") or 0.0) < 0
        semantic = _semantic_context(trade.get("entry_date"), ticker, trade.get("strategy"))
        row["semantic_context"] = semantic
        row["semantic_context_summary"] = {
            "news_item_count": semantic["news_item_count"],
            "llm_archive_available": semantic["llm_archive_available"],
            "earnings_snapshot_available": semantic["earnings_snapshot_available"],
            "event_snapshot_count": semantic["event_snapshot_count"],
            "is_earnings_strategy": semantic["is_earnings_strategy"],
        }
        rows.append(row)
    return result, rows


def _candidate_next_experiments(family_stats):
    candidates = []
    for family, stats in family_stats.items():
        windows = len([k for k, v in stats["loss_summary"]["window_counts"].items() if v])
        collateral = stats["collateral_to_loss_abs"]
        if stats["loss_count"] >= 3 and windows >= 2 and (collateral is None or collateral <= 0.75):
            candidates.append(
                {
                    "family": family,
                    "loss_count": stats["loss_count"],
                    "loss_pnl_abs": stats["loss_pnl_abs"],
                    "winner_collateral_count": stats["winner_collateral_count"],
                    "winner_collateral_pnl": stats["winner_collateral_pnl"],
                    "collateral_to_loss_abs": collateral,
                    "next_test_shape": (
                        "Default-off shadow replay only. Convert this family into an entry-observable "
                        "or explicitly early-lifecycle discriminator, then measure avoided losses, "
                        "winner collateral, and multi-window EV before any production rule."
                    ),
                }
            )
    return sorted(candidates, key=lambda row: (-(row["loss_pnl_abs"] or 0.0), row["collateral_to_loss_abs"] or 999.0))


def main():
    universe = get_universe()
    all_rows = []
    windows = OrderedDict()
    for label, cfg in WINDOWS.items():
        result, rows = _run_window(label, cfg, universe)
        windows[label] = {
            "window": {"start": cfg["start"], "end": cfg["end"], "state_note": cfg["state_note"]},
            "metrics": {
                "expected_value_score": result.get("expected_value_score"),
                "sharpe_daily": result.get("sharpe_daily"),
                "max_drawdown_pct": result.get("max_drawdown_pct"),
                "total_pnl": result.get("total_pnl"),
                "win_rate": result.get("win_rate"),
                "trade_count": result.get("total_trades"),
                "survival_rate": result.get("survival_rate"),
                "tail_loss_share": result.get("tail_loss_share"),
                "worst_trade_pct": result.get("worst_trade_pct"),
            },
        }
        all_rows.extend(rows)

    loss_rows = [row for row in all_rows if row["is_loss"]]
    loss_dates = Counter(row.get("entry_date") for row in loss_rows)
    clustered_loss_dates = {date for date, count in loss_dates.items() if date and count >= 2}
    for row in all_rows:
        row["family_flags"] = _classify(row, clustered_loss_dates)
        row["matching_families"] = [name for name, hit in row["family_flags"].items() if hit]
        row["primary_family"] = next((name for name in FAMILIES if row["family_flags"].get(name)), "unclassified") if row["is_loss"] else None

    loss_rows = [row for row in all_rows if row["is_loss"]]
    win_rows = [row for row in all_rows if not row["is_loss"]]
    family_stats = _family_stats(all_rows, loss_rows)
    primary_counts = Counter(row["primary_family"] for row in loss_rows)
    primary_loss_abs = Counter()
    for row in loss_rows:
        primary_loss_abs[row["primary_family"]] += -float(row.get("pnl") or 0.0)

    semantic_loss_coverage = {
        "loss_count": len(loss_rows),
        "with_news": sum(1 for row in loss_rows if row["semantic_context"]["news_item_count"] > 0),
        "with_llm_archive": sum(1 for row in loss_rows if row["semantic_context"]["llm_archive_available"]),
        "with_earnings_snapshot": sum(1 for row in loss_rows if row["semantic_context"]["earnings_snapshot_available"]),
        "with_event_snapshot": sum(1 for row in loss_rows if row["semantic_context"]["event_snapshot_count"] > 0),
        "earnings_strategy_losses": sum(1 for row in loss_rows if row["semantic_context"]["is_earnings_strategy"]),
    }
    false_positive_rows = [
        row
        for row in loss_rows
        if row["family_flags"].get("low_mfe_stopout") or row["family_flags"].get("failed_early_followthrough")
    ]
    exit_failure_rows = [
        row
        for row in loss_rows
        if row["family_flags"].get("moderate_mfe_full_reversal") or row["family_flags"].get("exit_failure_after_mfe")
    ]

    compact_losses = [
        {
            "window": row["window"],
            "ticker": row["ticker"],
            "strategy": row["strategy"],
            "sector": row.get("sector"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "exit_reason": row.get("exit_reason"),
            "pnl": _round(row.get("pnl"), 2),
            "pnl_pct_net": row.get("pnl_pct_net"),
            "initial_risk_pct": row.get("initial_risk_pct"),
            "mfe_pct": row.get("mfe_pct"),
            "mfe_r": row.get("mfe_r"),
            "target_progress": row.get("target_progress"),
            "d2_excess_vs_spy": row.get("d2_excess_vs_spy"),
            "worst_overnight_gap_pct": row.get("worst_overnight_gap_pct"),
            "stock_vs_sector_return": row.get("stock_vs_sector_return"),
            "sector_vs_spy_return": row.get("sector_vs_spy_return"),
            "primary_family": row.get("primary_family"),
            "matching_families": row.get("matching_families"),
            "semantic_context": row.get("semantic_context"),
        }
        for row in loss_rows
    ]

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "bad trade hold-quality taxonomy",
        "strategy_behavior_changed": False,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
        },
        "historical_guardrail_check": {
            "prior_hold_quality_audits": ["exp-20260427-004", "exp-20260430-002", "exp-20260501-011"],
            "new_information_this_run": "Refreshes the hold-quality taxonomy under the latest accepted stack and adds semantic context coverage plus explicit false-positive and exit-failure rollups.",
            "not_repeating_recent_rejected_mechanisms": [
                "No runner exit replay.",
                "No earnings sleeve re-enable.",
                "No short-pressure or options overlay.",
                "No threshold or filter change.",
            ],
        },
        "windows": windows,
        "family_definitions": FAMILIES,
        "aggregate": {
            "trade_count": len(all_rows),
            "loss_count": len(loss_rows),
            "win_count": len(win_rows),
            "loss_pnl_abs": _round(-sum(float(row.get("pnl") or 0.0) for row in loss_rows), 2),
            "winner_pnl": _round(sum(float(row.get("pnl") or 0.0) for row in win_rows), 2),
            "primary_family_counts": dict(primary_counts),
            "primary_family_loss_pnl_abs": {k: _round(v, 2) for k, v in primary_loss_abs.items()},
            "false_positive_signal_summary": _summary(false_positive_rows),
            "exit_failure_summary": _summary(exit_failure_rows),
            "tail_loss_source_top_quartile": [
                {
                    "window": row["window"],
                    "ticker": row["ticker"],
                    "entry_date": row["entry_date"],
                    "pnl": _round(row["pnl"], 2),
                    "primary_family": row["primary_family"],
                    "matching_families": row["matching_families"],
                }
                for row in sorted(loss_rows, key=lambda x: float(x.get("pnl") or 0.0))[: max(1, round(len(loss_rows) * 0.25))]
            ],
            "semantic_loss_coverage": semantic_loss_coverage,
            "clustered_loss_entry_dates": sorted(clustered_loss_dates),
        },
        "family_stats": family_stats,
        "loss_rows": compact_losses,
        "candidate_next_experiments": _candidate_next_experiments(family_stats),
        "decision": "observed_only",
        "interpretation": [
            "This is an attribution artifact, not a strategy change; post-entry path fields are not valid as direct entry filters.",
            "Future tests must estimate good-trade collateral before promoting any family into a default-off replay.",
            "LLM/news context remains coverage-limited; this audit records whether context exists but does not judge LLM value.",
        ],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(OUT_JSON)
    print(json.dumps(artifact["aggregate"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
