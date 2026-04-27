"""exp-20260426-006 trend_late_rollover subfamily audit.

Audit only. Replays the accepted A+B stack on the three fixed snapshot windows,
isolates losing `trend_late_rollover` trades, and measures repeated late exit
failure subfamilies plus winner collateral if a future fix zeroed a subfamily.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict

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

OUT_JSON = os.path.join(
    REPO_ROOT, "data", "exp_20260426_006_trend_late_rollover_audit.json"
)
LLM_FILE_TEMPLATE = "llm_prompt_resp_{date}.json"


def _safe_round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


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


def _risk_treatment(trade: dict) -> str:
    actual = float(trade.get("actual_risk_pct") or 0.0)
    base = float(trade.get("base_risk_pct") or 0.0)
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
    tags = []
    if any("dte" in key for key in keys):
        tags.append("earnings_proximity")
    if any("gap" in key for key in keys):
        tags.append("gap_sensitive")
    if any("near_high" in key for key in keys):
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


def _mechanism_class(days_held: int | None) -> str:
    hold_bucket = _hold_bucket(days_held)
    if hold_bucket == "instant":
        return "trend_instant_failure"
    if hold_bucket == "fast":
        return "trend_fast_failure"
    if hold_bucket == "followthrough":
        return "trend_failed_followthrough"
    return "trend_late_rollover"


def _news_context(entry_date: str, exit_date: str, ticker: str) -> dict:
    covered_dates = []
    negative_dates = []
    missing_dates = []
    upper = ticker.upper()
    for day in pd.date_range(entry_date, exit_date, freq="D"):
        decision = get_news_for_date(day.date(), os.path.join(REPO_ROOT, "data"))
        date_str = decision["date_str"]
        if decision["file_present"]:
            covered_dates.append(date_str)
        else:
            missing_dates.append(date_str)
        if upper in decision["t1_negative_tickers"]:
            negative_dates.append(date_str)
    total_days = len(covered_dates) + len(missing_dates)
    coverage_fraction = len(covered_dates) / total_days if total_days else 0.0
    return {
        "coverage_fraction": round(coverage_fraction, 4),
        "negative_dates": negative_dates,
        "covered_days": len(covered_dates),
        "missing_days": len(missing_dates),
        "archive_state": (
            "t1_negative_seen"
            if negative_dates
            else "archive_present"
            if covered_dates
            else "archive_missing"
        ),
    }


def _llm_context(entry_date: str) -> dict:
    date_str = entry_date.replace("-", "")
    path = os.path.join(REPO_ROOT, "data", LLM_FILE_TEMPLATE.format(date=date_str))
    return {
        "entry_day_archive_present": os.path.exists(path),
        "entry_day_archive_file": os.path.basename(path),
    }


def _target_bucket(trade: dict) -> str:
    target = trade.get("target_mult_used")
    if target is None:
        return "unknown_target"
    return f"{float(target):.2f}ATR"


def _peak_bucket(peak_return_pct: float) -> str:
    if peak_return_pct <= 0:
        return "never_green"
    if peak_return_pct < 0.05:
        return "green_lt_5pct"
    if peak_return_pct < 0.15:
        return "green_5_to_15pct"
    return "green_ge_15pct"


def _giveback_bucket(giveback_pct: float) -> str:
    if giveback_pct < 0.05:
        return "giveback_lt_5pct"
    if giveback_pct < 0.15:
        return "giveback_5_to_15pct"
    return "giveback_ge_15pct"


def _target_progress_bucket(peak_return_pct: float, target_return_pct: float | None) -> str:
    if not target_return_pct or target_return_pct <= 0:
        return "unknown_target_progress"
    progress = peak_return_pct / target_return_pct
    if progress < 0.25:
        return "target_lt_25pct"
    if progress < 0.5:
        return "target_25_to_50pct"
    if progress < 1.0:
        return "target_50_to_100pct"
    return "target_ge_100pct"


def _late_state_key(row: dict) -> str:
    return " | ".join([
        row["sector"],
        row["risk_treatment"],
        row["event_proxy"],
        row["target_bucket"],
        row["peak_bucket"],
        row["giveback_bucket"],
        row["target_progress_bucket"],
        row["regime_exit_bucket"] or "unknown_regime",
    ])


def _extract_trade_path_stats(df: pd.DataFrame, entry_idx: int, exit_idx: int, entry_price: float):
    path = df.iloc[entry_idx:exit_idx + 1]
    high_col = "High" if "High" in path.columns else "high"
    low_col = "Low" if "Low" in path.columns else "low"
    peak_high = float(path[high_col].max())
    worst_low = float(path[low_col].min())
    peak_return_pct = (peak_high / entry_price) - 1.0
    worst_drawdown_pct = (worst_low / entry_price) - 1.0
    return peak_high, peak_return_pct, worst_drawdown_pct


def _build_row(window_label: str, trade: dict, ohlcv: dict) -> dict | None:
    if trade.get("strategy") != "trend_long":
        return None
    ticker = trade.get("ticker")
    df = ohlcv.get(ticker)
    if df is None:
        return None
    entry_idx = _date_index_after(df, trade.get("entry_date"))
    exit_idx = _date_index_after(df, trade.get("exit_date"))
    if entry_idx is None or exit_idx is None or exit_idx < entry_idx:
        return None

    entry_price = float(trade.get("entry_price") or 0.0)
    exit_price = float(trade.get("exit_price") or 0.0)
    if entry_price <= 0 or exit_price <= 0:
        return None

    days_held = exit_idx - entry_idx
    mechanism_class = _mechanism_class(days_held)
    sector = trade.get("sector") or "Unknown"
    risk_treatment = _risk_treatment(trade)
    event_proxy = _event_proxy(trade)
    target_bucket = _target_bucket(trade)
    peak_high, peak_return_pct, worst_drawdown_pct = _extract_trade_path_stats(
        df, entry_idx, exit_idx, entry_price
    )
    exit_return_pct = (exit_price / entry_price) - 1.0
    giveback_pct = peak_return_pct - exit_return_pct
    target_return_pct = None
    initial_risk_pct = trade.get("initial_risk_pct")
    target_mult_used = trade.get("target_mult_used")
    if initial_risk_pct is not None and target_mult_used is not None:
        target_return_pct = float(initial_risk_pct) * float(target_mult_used)

    row = {
        "window": window_label,
        "ticker": ticker,
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": round(float(trade.get("pnl") or 0.0), 2),
        "pnl_pct_net": _safe_round(trade.get("pnl_pct_net"), 6),
        "days_held_trading": days_held,
        "hold_bucket": _hold_bucket(days_held),
        "mechanism_class": mechanism_class,
        "sector": sector,
        "risk_treatment": risk_treatment,
        "event_proxy": event_proxy,
        "target_bucket": target_bucket,
        "peak_price": _safe_round(peak_high, 4),
        "peak_return_pct": _safe_round(peak_return_pct, 6),
        "exit_return_pct": _safe_round(exit_return_pct, 6),
        "giveback_pct": _safe_round(giveback_pct, 6),
        "worst_drawdown_pct": _safe_round(worst_drawdown_pct, 6),
        "target_return_pct": _safe_round(target_return_pct, 6),
        "target_progress": _safe_round(
            (peak_return_pct / target_return_pct) if target_return_pct else None,
            6,
        ),
        "peak_bucket": _peak_bucket(peak_return_pct),
        "giveback_bucket": _giveback_bucket(giveback_pct),
        "target_progress_bucket": _target_progress_bucket(
            peak_return_pct, target_return_pct
        ),
        "actual_risk_pct": _safe_round(trade.get("actual_risk_pct"), 6),
        "base_risk_pct": _safe_round(trade.get("base_risk_pct"), 6),
        "initial_risk_pct": _safe_round(initial_risk_pct, 6),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": _safe_round(trade.get("regime_exit_score"), 4),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
        "news_context": _news_context(trade.get("entry_date"), trade.get("exit_date"), ticker),
        "llm_context": _llm_context(trade.get("entry_date")),
    }
    row["late_state_key"] = _late_state_key(row)
    row["subfamily_key"] = " | ".join([mechanism_class, row["late_state_key"]])
    return row


def _outcome_bucket(row: dict) -> str:
    pnl = row["pnl"]
    if row["mechanism_class"] == "trend_late_rollover" and pnl < 0:
        return "late_rollover_loss"
    if pnl > 0:
        return "winner"
    if pnl < 0:
        return "other_loss"
    return "flat"


def _summarize_group(group_key: str, rows: list[dict], gross_loss: float) -> dict:
    late_losses = [
        row for row in rows
        if row["mechanism_class"] == "trend_late_rollover" and row["pnl"] < 0
    ]
    if not late_losses:
        return {}
    winners = [row for row in rows if row["pnl"] > 0]
    other_losses = [
        row for row in rows
        if row["pnl"] < 0 and row["mechanism_class"] != "trend_late_rollover"
    ]
    loss_total = round(sum(-row["pnl"] for row in late_losses), 2)
    winner_total = round(sum(row["pnl"] for row in winners), 2)
    news_missing = sum(
        1 for row in late_losses if row["news_context"]["archive_state"] == "archive_missing"
    )
    llm_present = sum(
        1 for row in late_losses if row["llm_context"]["entry_day_archive_present"]
    )
    peak_returns = [row["peak_return_pct"] for row in late_losses]
    givebacks = [row["giveback_pct"] for row in late_losses]
    return {
        "subfamily_key": group_key,
        "late_rollover_count": len(late_losses),
        "late_rollover_loss_total_usd": loss_total,
        "late_rollover_loss_share": (
            round(loss_total / gross_loss, 4) if gross_loss else 0.0
        ),
        "all_trade_count_same_subfamily": len(rows),
        "winner_count_same_subfamily": len(winners),
        "winner_pnl_same_subfamily_usd": winner_total,
        "other_loss_count_same_subfamily": len(other_losses),
        "other_loss_pnl_same_subfamily_usd": round(sum(row["pnl"] for row in other_losses), 2),
        "net_pnl_same_subfamily_usd": round(sum(row["pnl"] for row in rows), 2),
        "outcome_breakdown": dict(Counter(_outcome_bucket(row) for row in rows)),
        "kill_good_trade_count_if_zeroed": len(winners),
        "kill_good_pnl_usd_if_zeroed": winner_total,
        "median_peak_return_pct_on_losses": _safe_round(pd.Series(peak_returns).median(), 6),
        "median_giveback_pct_on_losses": _safe_round(pd.Series(givebacks).median(), 6),
        "windows_with_late_rollovers": sorted({row["window"] for row in late_losses}),
        "representative_loss_tickers": [row["ticker"] for row in late_losses[:5]],
        "representative_winner_tickers_same_subfamily": [row["ticker"] for row in winners[:5]],
        "news_archive_missing_late_rollover_count": news_missing,
        "llm_entry_archive_present_late_rollover_count": llm_present,
    }


def _rollup_dimension(rows: list[dict], dimension: str) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[dimension]].append(row)
    gross_loss = sum(-row["pnl"] for row in rows if row["pnl"] < 0)
    rollup = []
    for value, items in sorted(grouped.items()):
        winners = [row for row in items if row["pnl"] > 0]
        losses = [row for row in items if row["pnl"] < 0]
        rollup.append({
            dimension: value,
            "trade_count": len(items),
            "late_rollover_count": len(losses),
            "late_rollover_loss_total_usd": round(sum(-row["pnl"] for row in losses), 2),
            "late_rollover_loss_share": (
                round(sum(-row["pnl"] for row in losses) / gross_loss, 4)
                if gross_loss
                else 0.0
            ),
            "winner_count_same_bucket": len(winners),
            "winner_pnl_same_bucket_usd": round(sum(row["pnl"] for row in winners), 2),
            "windows": sorted({row["window"] for row in items}),
        })
    rollup.sort(
        key=lambda item: (
            -item["late_rollover_count"],
            -item["late_rollover_loss_total_usd"],
            str(item[dimension]),
        )
    )
    return rollup


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, cfg)
    trend_rows = []
    for trade in result.get("trades", []):
        row = _build_row(label, trade, ohlcv)
        if row:
            trend_rows.append(row)

    late_rows = [
        row for row in trend_rows
        if row["mechanism_class"] == "trend_late_rollover"
    ]
    late_losses = [row for row in late_rows if row["pnl"] < 0]
    grouped = defaultdict(list)
    for row in late_rows:
        grouped[row["subfamily_key"]].append(row)
    gross_loss = round(sum(-row["pnl"] for row in late_losses), 2)
    subfamily_rollup = []
    for subfamily_key, items in grouped.items():
        summary = _summarize_group(subfamily_key, items, gross_loss)
        if summary:
            subfamily_rollup.append(summary)
    subfamily_rollup.sort(
        key=lambda item: (
            -item["late_rollover_count"],
            -item["late_rollover_loss_total_usd"],
            item["subfamily_key"],
        )
    )

    top_losses = sorted(late_losses, key=lambda row: -abs(row["pnl"]))[:3]
    return {
        "window": label,
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
        "trend_trade_count": len(trend_rows),
        "late_trade_count": len(late_rows),
        "late_rollover_count": len(late_losses),
        "gross_late_rollover_loss_usd": gross_loss,
        "top_late_rollover_losses": [
            {
                "ticker": row["ticker"],
                "subfamily_key": row["subfamily_key"],
                "pnl": row["pnl"],
                "days_held_trading": row["days_held_trading"],
                "peak_return_pct": row["peak_return_pct"],
                "giveback_pct": row["giveback_pct"],
            }
            for row in top_losses
        ],
        "late_rows": late_rows,
        "late_rollover_rows": late_losses,
        "subfamily_rollup": subfamily_rollup,
        "sector_rollup": _rollup_dimension(late_rows, "sector"),
        "risk_treatment_rollup": _rollup_dimension(late_rows, "risk_treatment"),
        "event_proxy_rollup": _rollup_dimension(late_rows, "event_proxy"),
        "peak_bucket_rollup": _rollup_dimension(late_rows, "peak_bucket"),
        "giveback_bucket_rollup": _rollup_dimension(late_rows, "giveback_bucket"),
        "target_progress_bucket_rollup": _rollup_dimension(
            late_rows, "target_progress_bucket"
        ),
        "regime_exit_bucket_rollup": _rollup_dimension(late_rows, "regime_exit_bucket"),
    }


def _cross_window_rollup(windows: list[dict]) -> dict:
    late_losses = []
    all_late_rows = []
    for window in windows:
        late_losses.extend(window["late_rollover_rows"])
        all_late_rows.extend(window["late_rows"])

    grouped = defaultdict(list)
    for row in all_late_rows:
        grouped[row["subfamily_key"]].append(row)

    gross_loss = round(sum(-row["pnl"] for row in late_losses), 2)
    subfamily_rollup = []
    for subfamily_key, items in grouped.items():
        summary = _summarize_group(subfamily_key, items, gross_loss)
        if summary:
            subfamily_rollup.append(summary)
    subfamily_rollup.sort(
        key=lambda item: (
            -item["late_rollover_count"],
            -item["late_rollover_loss_total_usd"],
            item["subfamily_key"],
        )
    )
    repeated = [item for item in subfamily_rollup if item["late_rollover_count"] >= 2]

    return {
        "late_rollover_count": len(late_losses),
        "gross_late_rollover_loss_usd": gross_loss,
        "subfamily_rollup": subfamily_rollup,
        "repeated_subfamilies": repeated,
        "sector_rollup": _rollup_dimension(all_late_rows, "sector"),
        "risk_treatment_rollup": _rollup_dimension(all_late_rows, "risk_treatment"),
        "event_proxy_rollup": _rollup_dimension(all_late_rows, "event_proxy"),
        "peak_bucket_rollup": _rollup_dimension(all_late_rows, "peak_bucket"),
        "giveback_bucket_rollup": _rollup_dimension(all_late_rows, "giveback_bucket"),
        "target_progress_bucket_rollup": _rollup_dimension(
            all_late_rows, "target_progress_bucket"
        ),
        "regime_exit_bucket_rollup": _rollup_dimension(all_late_rows, "regime_exit_bucket"),
        "llm_entry_archive_present_count": sum(
            1 for row in late_losses if row["llm_context"]["entry_day_archive_present"]
        ),
        "news_archive_missing_count": sum(
            1 for row in late_losses if row["news_context"]["archive_state"] == "archive_missing"
        ),
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        audited = _audit_window(label, cfg, universe)
        windows.append(audited)
        top_subfamily = audited["subfamily_rollup"][0] if audited["subfamily_rollup"] else None
        if top_subfamily:
            print(
                f"[{label}] late_rollovers={audited['late_rollover_count']} "
                f"gross_loss={audited['gross_late_rollover_loss_usd']} "
                f"top_subfamily={top_subfamily['subfamily_key']} "
                f"count={top_subfamily['late_rollover_count']} "
                f"kill_good={top_subfamily['kill_good_trade_count_if_zeroed']}"
            )
        else:
            print(f"[{label}] no trend_late_rollover losses")

    payload_windows = []
    for window in windows:
        payload_windows.append({key: value for key, value in window.items()})

    payload = {
        "experiment_id": "exp-20260426-006",
        "status": "audit_only",
        "hypothesis": (
            "The accepted stack's trend_late_rollover losses cluster into reproducible "
            "late exit-failure subfamilies that can be counted without changing strategy logic."
        ),
        "single_causal_variable": "trend_late_rollover subfamily taxonomy for accepted-stack losers",
        "windows": payload_windows,
        "cross_window": _cross_window_rollup(windows),
        "notes": [
            "subfamily_key combines entry context with in-trade path state: peak progress, giveback, and exit regime.",
            "kill_good_* estimates the collateral damage of zeroing an entire late-rollover subfamily.",
            "news/LLM fields remain measurement-quality indicators, not causal proof, because archive coverage is sparse.",
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
