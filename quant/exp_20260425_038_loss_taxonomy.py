"""exp-20260426-001 loss attribution taxonomy audit.

Audit only. This script replays the current accepted stack on the three fixed
snapshot windows, clusters losing trades into reproducible failure families,
and measures how many good trades would be killed by a hypothetical family-wide
fix. No production strategy code is changed.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from statistics import median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from news_replay import get_news_for_date  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_038_loss_taxonomy.json")
LLM_FILE_TEMPLATE = "llm_prompt_resp_{date}.json"


def _scalar(value):
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _safe_round(value, digits=6):
    if value is None:
        return None
    return round(value, digits)


def _load_window(universe: list[str], cfg: dict):
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    ohlcv = engine._load_ohlcv_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    return result, ohlcv


def _date_index_after(df: pd.DataFrame, date: str):
    ts = pd.Timestamp(date)
    for idx, day in enumerate(df.index):
        if day >= ts:
            return idx
    return None


def _news_context(entry_date: str, exit_date: str, ticker: str) -> dict:
    covered_dates = []
    missing_dates = []
    negative_dates = []
    all_t1_dates = []
    for day in pd.date_range(entry_date, exit_date, freq="D"):
        decision = get_news_for_date(day.date(), os.path.join(REPO_ROOT, "data"))
        date_str = decision["date_str"]
        if decision["file_present"]:
            covered_dates.append(date_str)
        else:
            missing_dates.append(date_str)
        upper = ticker.upper()
        if upper in decision["all_t1_tickers"]:
            all_t1_dates.append(date_str)
        if upper in decision["t1_negative_tickers"]:
            negative_dates.append(date_str)
    total_days = len(covered_dates) + len(missing_dates)
    coverage = len(covered_dates) / total_days if total_days else 0.0
    if negative_dates:
        explain_bucket = "t1_negative_seen"
    elif covered_dates:
        explain_bucket = "archive_covered_no_negative"
    else:
        explain_bucket = "archive_missing"
    return {
        "coverage_fraction": round(coverage, 4),
        "covered_days": len(covered_dates),
        "missing_days": len(missing_dates),
        "t1_negative_dates": negative_dates,
        "all_t1_dates": all_t1_dates,
        "explain_bucket": explain_bucket,
    }


def _llm_context(entry_date: str) -> dict:
    date_str = entry_date.replace("-", "")
    path = os.path.join(REPO_ROOT, "data", LLM_FILE_TEMPLATE.format(date=date_str))
    return {
        "entry_day_archive_present": os.path.exists(path),
        "entry_day_archive_file": os.path.basename(path),
    }


def _risk_treatment(trade: dict) -> str:
    actual = trade.get("actual_risk_pct") or 0.0
    base = trade.get("base_risk_pct") or 0.0
    if base <= 0:
        return "unknown_risk"
    ratio = actual / base
    if ratio <= 0:
        return "zero_risk"
    if ratio < 1:
        return "reduced_risk"
    return "full_risk"


def _event_proxy(trade: dict) -> str:
    keys = sorted((trade.get("sizing_multipliers") or {}).keys())
    has_dte = any("dte" in key for key in keys)
    has_gap = any("gap" in key for key in keys)
    has_near_high = any("near_high" in key for key in keys)
    tags = []
    if has_dte:
        tags.append("earnings_proximity")
    if has_gap:
        tags.append("gap_sensitive")
    if has_near_high:
        tags.append("near_high")
    return "+".join(tags) if tags else "plain"


def _hold_bucket(days_held: int | None) -> str:
    if days_held is None:
        return "unknown_hold"
    if days_held <= 1:
        return "instant"
    if days_held <= 5:
        return "fast"
    if days_held <= 15:
        return "followthrough"
    return "late"


def _mechanism_class(strategy: str, days_held: int | None) -> str:
    hold_bucket = _hold_bucket(days_held)
    if strategy == "breakout_long":
        if hold_bucket in {"instant", "fast"}:
            return "breakout_fast_reversal"
        if hold_bucket == "followthrough":
            return "breakout_failed_followthrough"
        return "breakout_late_rollover"
    if strategy == "trend_long":
        if hold_bucket == "instant":
            return "trend_instant_failure"
        if hold_bucket == "fast":
            return "trend_fast_failure"
        if hold_bucket == "followthrough":
            return "trend_failed_followthrough"
        return "trend_late_rollover"
    return f"{strategy or 'unknown'}_{hold_bucket}"


def _audit_trade(window_label: str, trade: dict, ohlcv: dict) -> dict | None:
    ticker = trade.get("ticker")
    df = ohlcv.get(ticker)
    if df is None:
        return None
    entry_idx = _date_index_after(df, trade.get("entry_date"))
    exit_idx = _date_index_after(df, trade.get("exit_date"))
    if entry_idx is None or exit_idx is None or exit_idx < entry_idx:
        return None

    days_held = exit_idx - entry_idx
    strategy = trade.get("strategy") or "unknown"
    sector = trade.get("sector") or "Unknown"
    risk_treatment = _risk_treatment(trade)
    event_proxy = _event_proxy(trade)
    mechanism = _mechanism_class(strategy, days_held)
    family_key = " | ".join([
        strategy,
        sector,
        mechanism,
        risk_treatment,
        event_proxy,
    ])
    news = _news_context(trade.get("entry_date"), trade.get("exit_date"), ticker)
    llm = _llm_context(trade.get("entry_date"))
    pnl = trade.get("pnl") or 0.0
    pnl_pct = trade.get("pnl_pct_net")

    return {
        "window": window_label,
        "ticker": ticker,
        "strategy": strategy,
        "sector": sector,
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "days_held_trading": days_held,
        "hold_bucket": _hold_bucket(days_held),
        "mechanism_class": mechanism,
        "risk_treatment": risk_treatment,
        "event_proxy": event_proxy,
        "family_key": family_key,
        "pnl": round(pnl, 2),
        "pnl_pct_net": _safe_round(pnl_pct, 6),
        "loss_abs_usd": round(abs(pnl), 2) if pnl < 0 else 0.0,
        "actual_risk_pct": _safe_round(trade.get("actual_risk_pct"), 6),
        "base_risk_pct": _safe_round(trade.get("base_risk_pct"), 6),
        "target_mult_used": trade.get("target_mult_used"),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": _safe_round(trade.get("regime_exit_score"), 4),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
        "news_context": news,
        "llm_context": llm,
    }


def _window_family_rollup(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["family_key"]].append(row)

    gross_losses = sum(-row["pnl"] for row in rows if row["pnl"] < 0)
    rollup = []
    for family_key, items in grouped.items():
        losses = [row for row in items if row["pnl"] < 0]
        wins = [row for row in items if row["pnl"] > 0]
        if not losses:
            continue
        total_loss = round(sum(-row["pnl"] for row in losses), 2)
        total_win = round(sum(row["pnl"] for row in wins), 2)
        llm_present = sum(
            1 for row in items if row["llm_context"]["entry_day_archive_present"]
        )
        news_negative = sum(
            1 for row in items
            if row["news_context"]["explain_bucket"] == "t1_negative_seen"
        )
        news_missing = sum(
            1 for row in items
            if row["news_context"]["explain_bucket"] == "archive_missing"
        )
        rollup.append({
            "family_key": family_key,
            "loss_count": len(losses),
            "win_count": len(wins),
            "trade_count": len(items),
            "loss_total_usd": total_loss,
            "win_total_usd": total_win,
            "net_total_usd": round(total_win - total_loss, 2),
            "gross_loss_share": round(total_loss / gross_losses, 4) if gross_losses else 0.0,
            "median_days_held_trading": median(
                row["days_held_trading"] for row in items
            ),
            "kill_good_trade_count_if_zeroed": len(wins),
            "kill_good_pnl_usd_if_zeroed": total_win,
            "llm_entry_archive_present_count": llm_present,
            "news_negative_trade_count": news_negative,
            "news_archive_missing_trade_count": news_missing,
            "representative_tickers": sorted({row["ticker"] for row in items}),
            "windows": sorted({row["window"] for row in items}),
        })
    rollup.sort(key=lambda item: (-item["loss_count"], -item["loss_total_usd"], item["family_key"]))
    return rollup


def _strategy_rollup(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["strategy"]].append(row)
    result = []
    for strategy, items in sorted(grouped.items()):
        losses = [row for row in items if row["pnl"] < 0]
        wins = [row for row in items if row["pnl"] > 0]
        result.append({
            "strategy": strategy,
            "trade_count": len(items),
            "loss_count": len(losses),
            "win_count": len(wins),
            "loss_total_usd": round(sum(-row["pnl"] for row in losses), 2),
            "win_total_usd": round(sum(row["pnl"] for row in wins), 2),
            "top_loss_mechanisms": Counter(
                row["mechanism_class"] for row in losses
            ).most_common(3),
        })
    return result


def _mechanism_rollup(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["mechanism_class"]].append(row)
    result = []
    gross_losses = sum(-row["pnl"] for row in rows if row["pnl"] < 0)
    for mechanism, items in sorted(grouped.items()):
        losses = [row for row in items if row["pnl"] < 0]
        wins = [row for row in items if row["pnl"] > 0]
        if not losses:
            continue
        loss_total = round(sum(-row["pnl"] for row in losses), 2)
        win_total = round(sum(row["pnl"] for row in wins), 2)
        result.append({
            "mechanism_class": mechanism,
            "loss_count": len(losses),
            "win_count": len(wins),
            "trade_count": len(items),
            "loss_total_usd": loss_total,
            "win_total_usd": win_total,
            "gross_loss_share": round(loss_total / gross_losses, 4) if gross_losses else 0.0,
            "kill_good_trade_count_if_zeroed": len(wins),
            "kill_good_pnl_usd_if_zeroed": win_total,
            "representative_families": sorted({row["family_key"] for row in items})[:5],
        })
    result.sort(key=lambda item: (-item["loss_count"], -item["loss_total_usd"], item["mechanism_class"]))
    return result


def _window_summary(result: dict, rows: list[dict]) -> dict:
    losses = [row for row in rows if row["pnl"] < 0]
    news_negative = sum(
        1 for row in losses if row["news_context"]["explain_bucket"] == "t1_negative_seen"
    )
    news_missing = sum(
        1 for row in losses if row["news_context"]["explain_bucket"] == "archive_missing"
    )
    llm_present = sum(
        1 for row in losses if row["llm_context"]["entry_day_archive_present"]
    )
    tail_sorted = sorted(losses, key=lambda row: row["loss_abs_usd"], reverse=True)
    top3 = tail_sorted[:3]
    gross_loss = sum(row["loss_abs_usd"] for row in losses)
    top3_loss = sum(row["loss_abs_usd"] for row in top3)
    return {
        "baseline": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_return_pct": (result.get("benchmarks") or {}).get(
                "strategy_total_return_pct"
            ),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
        },
        "loss_count": len(losses),
        "gross_loss_usd": round(gross_loss, 2),
        "top3_loss_share": round(top3_loss / gross_loss, 4) if gross_loss else 0.0,
        "top3_losses": [
            {
                "ticker": row["ticker"],
                "strategy": row["strategy"],
                "sector": row["sector"],
                "family_key": row["family_key"],
                "pnl": row["pnl"],
                "days_held_trading": row["days_held_trading"],
            }
            for row in top3
        ],
        "news_context_on_losses": {
            "t1_negative_seen_count": news_negative,
            "archive_missing_count": news_missing,
        },
        "llm_entry_archive_present_on_losses": llm_present,
    }


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, cfg)
    rows = []
    for trade in result.get("trades", []):
        item = _audit_trade(label, trade, ohlcv)
        if item:
            rows.append(item)
    family_rollup = _window_family_rollup(rows)
    return {
        "window": label,
        "summary": _window_summary(result, rows),
        "mechanism_rollup": _mechanism_rollup(rows),
        "strategy_rollup": _strategy_rollup(rows),
        "family_rollup": family_rollup,
        "loss_rows": [row for row in rows if row["pnl"] < 0],
        "all_rows": rows,
    }


def _cross_window_rollup(windows: list[dict]) -> dict:
    rows = []
    for window in windows:
        rows.extend(window["all_rows"])
    family_rollup = _window_family_rollup(rows)
    repeated = [item for item in family_rollup if item["loss_count"] >= 2]
    return {
        "mechanism_rollup": _mechanism_rollup(rows),
        "family_rollup": family_rollup,
        "repeated_loss_families": repeated[:10],
        "strategy_rollup": _strategy_rollup(rows),
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        audited = _audit_window(label, cfg, universe)
        windows.append(audited)
        summary = audited["summary"]
        top_family = audited["family_rollup"][0] if audited["family_rollup"] else None
        if top_family:
            print(
                f"[{label}] losses={summary['loss_count']} "
                f"gross_loss={summary['gross_loss_usd']} "
                f"top3_share={summary['top3_loss_share']} "
                f"top_family={top_family['family_key']} "
                f"count={top_family['loss_count']} "
                f"kill_good={top_family['kill_good_trade_count_if_zeroed']}"
            )
        else:
            print(f"[{label}] no loss families found")

    payload = {
        "experiment_id": "exp-20260426-001",
        "status": "audit_only",
        "hypothesis": (
            "Current accepted-stack losses cluster into reproducible failure "
            "families that can be counted without changing strategy logic."
        ),
        "single_causal_variable": "bad-trade failure family taxonomy for current accepted-stack losers",
        "windows": windows,
        "cross_window": _cross_window_rollup(windows),
        "notes": [
            "family_key is the intended closeout unit for future loss-attribution experiments.",
            "kill_good_* fields estimate collateral damage if a future fix simply removed an entire family.",
            "news_context is archive-based and should be treated as missing when coverage is sparse.",
            "llm_context only checks whether an entry-day replay file exists; it does not imply candidate-level alignment.",
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
