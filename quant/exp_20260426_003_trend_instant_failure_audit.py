"""exp-20260426-004 trend_instant_failure subfamily audit.

Audit only. Replays the accepted A+B stack on the three fixed snapshot windows,
isolates losing `trend_instant_failure` trades, and measures their repeated
entry-context subfamilies plus the winner collateral a future context-wide fix
would kill.
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
    REPO_ROOT, "data", "exp_20260426_003_trend_instant_failure_audit.json"
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

    days_held = exit_idx - entry_idx
    sector = trade.get("sector") or "Unknown"
    risk_treatment = _risk_treatment(trade)
    event_proxy = _event_proxy(trade)
    target_bucket = _target_bucket(trade)
    mechanism_class = _mechanism_class(days_held)
    context_key = " | ".join([
        sector,
        risk_treatment,
        event_proxy,
        target_bucket,
    ])
    subfamily_key = " | ".join([mechanism_class, context_key])
    pnl = round(float(trade.get("pnl") or 0.0), 2)

    return {
        "window": window_label,
        "ticker": ticker,
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": pnl,
        "pnl_pct_net": _safe_round(trade.get("pnl_pct_net"), 6),
        "days_held_trading": days_held,
        "hold_bucket": _hold_bucket(days_held),
        "mechanism_class": mechanism_class,
        "sector": sector,
        "risk_treatment": risk_treatment,
        "event_proxy": event_proxy,
        "target_bucket": target_bucket,
        "context_key": context_key,
        "subfamily_key": subfamily_key,
        "actual_risk_pct": _safe_round(trade.get("actual_risk_pct"), 6),
        "base_risk_pct": _safe_round(trade.get("base_risk_pct"), 6),
        "initial_risk_pct": _safe_round(trade.get("initial_risk_pct"), 6),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": _safe_round(trade.get("regime_exit_score"), 4),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
        "news_context": _news_context(trade.get("entry_date"), trade.get("exit_date"), ticker),
        "llm_context": _llm_context(trade.get("entry_date")),
    }


def _outcome_bucket(row: dict) -> str:
    pnl = row["pnl"]
    if row["mechanism_class"] == "trend_instant_failure" and pnl < 0:
        return "instant_failure_loss"
    if pnl > 0:
        return "winner"
    if pnl < 0:
        return "other_loss"
    return "flat"


def _summarize_context_group(context_key: str, rows: list[dict], gross_instant_loss: float) -> dict:
    instant_losses = [
        row for row in rows
        if row["mechanism_class"] == "trend_instant_failure" and row["pnl"] < 0
    ]
    if not instant_losses:
        return {}
    winners = [row for row in rows if row["pnl"] > 0]
    other_losses = [
        row for row in rows
        if row["pnl"] < 0 and row["mechanism_class"] != "trend_instant_failure"
    ]
    instant_loss_total = round(sum(-row["pnl"] for row in instant_losses), 2)
    winner_total = round(sum(row["pnl"] for row in winners), 2)
    news_missing = sum(
        1 for row in instant_losses if row["news_context"]["archive_state"] == "archive_missing"
    )
    llm_present = sum(
        1 for row in instant_losses if row["llm_context"]["entry_day_archive_present"]
    )
    return {
        "context_key": context_key,
        "instant_failure_count": len(instant_losses),
        "instant_failure_loss_total_usd": instant_loss_total,
        "instant_failure_loss_share": (
            round(instant_loss_total / gross_instant_loss, 4) if gross_instant_loss else 0.0
        ),
        "all_trade_count_same_context": len(rows),
        "winner_count_same_context": len(winners),
        "winner_pnl_same_context_usd": winner_total,
        "other_loss_count_same_context": len(other_losses),
        "other_loss_pnl_same_context_usd": round(sum(row["pnl"] for row in other_losses), 2),
        "net_pnl_same_context_usd": round(sum(row["pnl"] for row in rows), 2),
        "outcome_breakdown": dict(Counter(_outcome_bucket(row) for row in rows)),
        "kill_good_trade_count_if_zeroed": len(winners),
        "kill_good_pnl_usd_if_zeroed": winner_total,
        "windows_with_instant_failures": sorted({row["window"] for row in instant_losses}),
        "representative_instant_failure_tickers": [row["ticker"] for row in instant_losses[:5]],
        "representative_winner_tickers_same_context": [row["ticker"] for row in winners[:5]],
        "news_archive_missing_instant_failure_count": news_missing,
        "llm_entry_archive_present_instant_failure_count": llm_present,
    }


def _rollup_dimension(rows: list[dict], dimension: str) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[dimension]].append(row)
    gross_instant_loss = sum(-row["pnl"] for row in rows if row["pnl"] < 0)
    rollup = []
    for value, items in sorted(grouped.items()):
        winners = [row for row in items if row["pnl"] > 0]
        losses = [row for row in items if row["pnl"] < 0]
        rollup.append({
            dimension: value,
            "trade_count": len(items),
            "instant_failure_count": len(losses),
            "instant_failure_loss_total_usd": round(sum(-row["pnl"] for row in losses), 2),
            "instant_failure_loss_share": (
                round(sum(-row["pnl"] for row in losses) / gross_instant_loss, 4)
                if gross_instant_loss
                else 0.0
            ),
            "winner_count_same_bucket": len(winners),
            "winner_pnl_same_bucket_usd": round(sum(row["pnl"] for row in winners), 2),
            "windows": sorted({row["window"] for row in items}),
        })
    rollup.sort(
        key=lambda item: (
            -item["instant_failure_count"],
            -item["instant_failure_loss_total_usd"],
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

    instant_rows = [
        row for row in trend_rows
        if row["mechanism_class"] == "trend_instant_failure" and row["pnl"] < 0
    ]
    grouped = defaultdict(list)
    for row in trend_rows:
        grouped[row["context_key"]].append(row)
    gross_instant_loss = round(sum(-row["pnl"] for row in instant_rows), 2)
    context_rollup = []
    for context_key, items in grouped.items():
        summary = _summarize_context_group(context_key, items, gross_instant_loss)
        if summary:
            context_rollup.append(summary)
    context_rollup.sort(
        key=lambda item: (
            -item["instant_failure_count"],
            -item["instant_failure_loss_total_usd"],
            item["context_key"],
        )
    )

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
        "instant_failure_count": len(instant_rows),
        "gross_instant_failure_loss_usd": gross_instant_loss,
        "all_trend_rows": trend_rows,
        "instant_failure_rows": instant_rows,
        "context_rollup": context_rollup,
        "sector_rollup": _rollup_dimension(instant_rows, "sector"),
        "risk_treatment_rollup": _rollup_dimension(instant_rows, "risk_treatment"),
        "event_proxy_rollup": _rollup_dimension(instant_rows, "event_proxy"),
        "target_bucket_rollup": _rollup_dimension(instant_rows, "target_bucket"),
    }


def _cross_window_rollup(windows: list[dict]) -> dict:
    instant_rows = []
    for window in windows:
        instant_rows.extend(window["instant_failure_rows"])
    full_trend_rows = []
    for window in windows:
        full_trend_rows.extend(window["all_trend_rows"])

    grouped = defaultdict(list)
    for row in full_trend_rows:
        grouped[row["context_key"]].append(row)

    gross_instant_loss = round(sum(-row["pnl"] for row in instant_rows), 2)
    context_rollup = []
    for context_key, items in grouped.items():
        summary = _summarize_context_group(context_key, items, gross_instant_loss)
        if summary:
            context_rollup.append(summary)
    context_rollup.sort(
        key=lambda item: (
            -item["instant_failure_count"],
            -item["instant_failure_loss_total_usd"],
            item["context_key"],
        )
    )

    repeated = [item for item in context_rollup if item["instant_failure_count"] >= 2]
    return {
        "instant_failure_count": len(instant_rows),
        "gross_instant_failure_loss_usd": gross_instant_loss,
        "context_rollup": context_rollup,
        "repeated_contexts": repeated,
        "sector_rollup": _rollup_dimension(instant_rows, "sector"),
        "risk_treatment_rollup": _rollup_dimension(instant_rows, "risk_treatment"),
        "event_proxy_rollup": _rollup_dimension(instant_rows, "event_proxy"),
        "target_bucket_rollup": _rollup_dimension(instant_rows, "target_bucket"),
        "llm_entry_archive_present_count": sum(
            1 for row in instant_rows if row["llm_context"]["entry_day_archive_present"]
        ),
        "news_archive_missing_count": sum(
            1 for row in instant_rows if row["news_context"]["archive_state"] == "archive_missing"
        ),
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        audited = _audit_window(label, cfg, universe)
        windows.append(audited)
        top_context = audited["context_rollup"][0] if audited["context_rollup"] else None
        if top_context:
            print(
                f"[{label}] instant_failures={audited['instant_failure_count']} "
                f"gross_loss={audited['gross_instant_failure_loss_usd']} "
                f"top_context={top_context['context_key']} "
                f"count={top_context['instant_failure_count']} "
                f"kill_good={top_context['kill_good_trade_count_if_zeroed']}"
            )
        else:
            print(f"[{label}] no trend_instant_failure losses")

    payload_windows = []
    for window in windows:
        payload_windows.append({
            key: value for key, value in window.items() if key != "all_trend_rows"
        })

    payload = {
        "experiment_id": "exp-20260426-004",
        "status": "audit_only",
        "hypothesis": (
            "The accepted stack's dominant repeated loser family is "
            "trend_instant_failure, and its internal subfamilies can be measured "
            "reproducibly without changing strategy logic."
        ),
        "single_causal_variable": "trend_instant_failure subfamily taxonomy for accepted-stack losers",
        "windows": payload_windows,
        "cross_window": _cross_window_rollup(windows),
        "notes": [
            "context_key is entry-context only: sector, realized risk treatment, event proxy, and target bucket.",
            "kill_good_* fields estimate the collateral damage of zeroing an entire entry-context, not just a single losing ticker.",
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
