"""exp-20260426-007 breakout failure-family audit.

Audit only. Replays the accepted A+B stack on the three fixed snapshot windows,
isolates `breakout_long` trades, and measures repeated loser families plus the
winner collateral a future family-wide fix would kill.
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
    REPO_ROOT, "data", "exp_20260426_007_breakout_failure_audit.json"
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
    if days_held <= 3:
        return "fast"
    if days_held <= 15:
        return "followthrough"
    return "late"


def _mechanism_class(days_held: int | None) -> str:
    hold_bucket = _hold_bucket(days_held)
    if hold_bucket == "fast":
        return "breakout_fast_reversal"
    if hold_bucket == "followthrough":
        return "breakout_failed_followthrough"
    return "breakout_late_rollover"


def _false_positive_family(mechanism_class: str, risk_treatment: str, event_proxy: str) -> str:
    if risk_treatment == "reduced_risk" and event_proxy == "earnings_proximity":
        return "event_sensitive_earnings_false_positive"
    if risk_treatment == "reduced_risk" and event_proxy == "gap_sensitive+near_high":
        return "event_sensitive_gap_near_high_false_positive"
    if risk_treatment == "full_risk" and event_proxy == "plain":
        if mechanism_class == "breakout_fast_reversal":
            return "plain_full_risk_fast_reversal"
        if mechanism_class == "breakout_failed_followthrough":
            return "plain_full_risk_failed_followthrough"
        return "plain_full_risk_late_rollover"
    return f"{risk_treatment}_{event_proxy}_{mechanism_class}"


def _target_bucket(trade: dict) -> str:
    target = trade.get("target_mult_used")
    if target is None:
        return "unknown_target"
    return f"{float(target):.2f}ATR"


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


def _build_row(window_label: str, trade: dict, ohlcv: dict) -> dict | None:
    if trade.get("strategy") != "breakout_long":
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
    false_positive_family = _false_positive_family(
        mechanism_class, risk_treatment, event_proxy
    )
    coarse_key = " | ".join([risk_treatment, event_proxy])
    context_key = " | ".join([sector, risk_treatment, event_proxy, target_bucket])
    subfamily_key = " | ".join([mechanism_class, coarse_key])
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
        "false_positive_family": false_positive_family,
        "sector": sector,
        "risk_treatment": risk_treatment,
        "event_proxy": event_proxy,
        "target_bucket": target_bucket,
        "coarse_key": coarse_key,
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


def _loss_only_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["pnl"] < 0]


def _rollup(rows: list[dict], key_name: str, candidate_pool: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in candidate_pool:
        grouped[row[key_name]].append(row)

    gross_losses = round(sum(-row["pnl"] for row in rows if row["pnl"] < 0), 2)
    rollup = []
    for key, items in grouped.items():
        losses = [row for row in items if row["pnl"] < 0]
        if not losses:
            continue
        wins = [row for row in items if row["pnl"] > 0]
        loss_total = round(sum(-row["pnl"] for row in losses), 2)
        winner_total = round(sum(row["pnl"] for row in wins), 2)
        rollup.append({
            key_name: key,
            "loss_count": len(losses),
            "loss_total_usd": loss_total,
            "gross_loss_share": round(loss_total / gross_losses, 4) if gross_losses else 0.0,
            "winner_count_same_bucket": len(wins),
            "winner_pnl_same_bucket_usd": winner_total,
            "kill_good_trade_count_if_zeroed": len(wins),
            "kill_good_pnl_usd_if_zeroed": winner_total,
            "net_pnl_same_bucket_usd": round(sum(row["pnl"] for row in items), 2),
            "windows": sorted({row["window"] for row in losses}),
            "representative_loss_tickers": [row["ticker"] for row in losses[:5]],
            "representative_winner_tickers": [row["ticker"] for row in wins[:5]],
            "news_archive_missing_loss_count": sum(
                1 for row in losses if row["news_context"]["archive_state"] == "archive_missing"
            ),
            "news_negative_loss_count": sum(
                1 for row in losses if row["news_context"]["archive_state"] == "t1_negative_seen"
            ),
            "llm_entry_archive_present_loss_count": sum(
                1 for row in losses if row["llm_context"]["entry_day_archive_present"]
            ),
        })
    rollup.sort(
        key=lambda item: (
            -item["loss_count"],
            -item["loss_total_usd"],
            str(item[key_name]),
        )
    )
    return rollup


def _window_summary(result: dict, rows: list[dict]) -> dict:
    losses = _loss_only_rows(rows)
    gross_loss = round(sum(-row["pnl"] for row in losses), 2)
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
        "breakout_trade_count": len(rows),
        "breakout_loss_count": len(losses),
        "breakout_gross_loss_usd": gross_loss,
        "llm_entry_archive_present_on_losses": sum(
            1 for row in losses if row["llm_context"]["entry_day_archive_present"]
        ),
        "news_archive_missing_on_losses": sum(
            1 for row in losses if row["news_context"]["archive_state"] == "archive_missing"
        ),
        "news_negative_on_losses": sum(
            1 for row in losses if row["news_context"]["archive_state"] == "t1_negative_seen"
        ),
    }


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, cfg)
    rows = []
    for trade in result.get("trades", []):
        row = _build_row(label, trade, ohlcv)
        if row:
            rows.append(row)
    losses = _loss_only_rows(rows)
    return {
        "window": label,
        "summary": _window_summary(result, rows),
        "loss_rows": losses,
        "all_rows": rows,
        "mechanism_rollup": _rollup(losses, "mechanism_class", rows),
        "coarse_rollup": _rollup(losses, "coarse_key", rows),
        "subfamily_rollup": _rollup(losses, "subfamily_key", rows),
        "false_positive_family_rollup": _rollup(losses, "false_positive_family", rows),
        "context_rollup": _rollup(losses, "context_key", rows),
        "sector_rollup": _rollup(losses, "sector", rows),
    }


def _cross_window_rollup(windows: list[dict]) -> dict:
    all_rows = []
    for window in windows:
        all_rows.extend(window["all_rows"])
    losses = _loss_only_rows(all_rows)
    coarse_rollup = _rollup(losses, "coarse_key", all_rows)
    false_positive_rollup = _rollup(losses, "false_positive_family", all_rows)
    subfamily_rollup = _rollup(losses, "subfamily_key", all_rows)
    context_rollup = _rollup(losses, "context_key", all_rows)
    return {
        "breakout_loss_count": len(losses),
        "breakout_gross_loss_usd": round(sum(-row["pnl"] for row in losses), 2),
        "mechanism_rollup": _rollup(losses, "mechanism_class", all_rows),
        "coarse_rollup": coarse_rollup,
        "false_positive_family_rollup": false_positive_rollup,
        "subfamily_rollup": subfamily_rollup,
        "context_rollup": context_rollup,
        "sector_rollup": _rollup(losses, "sector", all_rows),
        "repeated_coarse_families": [
            item for item in coarse_rollup if item["loss_count"] >= 2
        ],
        "repeated_false_positive_families": [
            item for item in false_positive_rollup if item["loss_count"] >= 2
        ],
        "repeated_subfamilies": [
            item for item in subfamily_rollup if item["loss_count"] >= 2
        ],
        "zero_collateral_repeated_candidates": [
            item
            for item in coarse_rollup
            if item["loss_count"] >= 2 and item["winner_count_same_bucket"] == 0
        ],
        "llm_entry_archive_present_loss_count": sum(
            1 for row in losses if row["llm_context"]["entry_day_archive_present"]
        ),
        "news_archive_missing_loss_count": sum(
            1 for row in losses if row["news_context"]["archive_state"] == "archive_missing"
        ),
        "news_negative_loss_count": sum(
            1 for row in losses if row["news_context"]["archive_state"] == "t1_negative_seen"
        ),
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        audited = _audit_window(label, cfg, universe)
        windows.append(audited)
        top_coarse = audited["coarse_rollup"][0] if audited["coarse_rollup"] else None
        if top_coarse:
            print(
                f"[{label}] breakout_losses={audited['summary']['breakout_loss_count']} "
                f"gross_loss={audited['summary']['breakout_gross_loss_usd']} "
                f"top_coarse={top_coarse['coarse_key']} "
                f"count={top_coarse['loss_count']} "
                f"kill_good={top_coarse['kill_good_trade_count_if_zeroed']}"
            )
        else:
            print(f"[{label}] no breakout losses")

    payload = {
        "experiment_id": "exp-20260426-007",
        "status": "audit_only",
        "hypothesis": (
            "The accepted stack's breakout losers still cluster into a reproducible "
            "false-positive subfamily that can be counted without changing strategy logic."
        ),
        "single_causal_variable": "breakout false-positive failure family taxonomy for accepted-stack losers",
        "windows": windows,
        "cross_window": _cross_window_rollup(windows),
        "notes": [
            "coarse_key is the intended first-pass family for future breakout loss attribution: risk treatment plus event proxy.",
            "false_positive_family adds a small amount of mechanism labeling without introducing new production rules.",
            "kill_good_* fields estimate the collateral damage of zeroing a whole family; they are not a recommendation to implement that fix.",
            "news/LLM fields remain measurement-quality indicators because historical archive coverage is sparse on breakout losses too.",
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
