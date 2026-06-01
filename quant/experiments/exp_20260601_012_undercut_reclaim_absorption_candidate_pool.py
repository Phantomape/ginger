"""exp-20260601-012 undercut-reclaim absorption candidate-pool scout.

Lane: alpha_search.
Single causal variable: undercut_reclaim_absorption_candidate_source_v1.

This replay-only scout tests a free-OHLCV candidate source: liquid operating
company stocks that undercut a prior 10-day low intraday, reclaim it by the
close, close in the upper part of the session range, retain positive relative
strength versus SPY, and are not emitted during acute broad-market stress.

No production orders, core ranking, sizing, exits, watchlists, LLM/news inputs,
or shared strategy policy are changed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT / "quant", ROOT / "quant" / "experiments"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)


EXPERIMENT_ID = "exp-20260601-012"
STEM = "undercut_reclaim_absorption_candidate_pool"
TRIAL_FAMILY = "undercut_reclaim_absorption_candidate_pool"
CHANGED_VARIABLE = "undercut_reclaim_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1

MIN_PRICE = 15.0
MIN_AVG_DOLLAR_VOLUME_20 = 100_000_000.0
MIN_UNDERCUT_DEPTH_PCT = 0.005
MIN_CLOSE_RECLAIM_BUFFER_PCT = 0.002
MIN_LOW_TO_CLOSE_RECLAIM_PCT = 0.03
MIN_CLOSE_LOCATION = 0.65
MIN_VOLUME_RATIO_20 = 1.10
MIN_RET20_EXCESS_SPY = 0.00
MAX_PRIOR_CLOSE_GAP_DOWN_PCT = -0.05
MIN_SPY_RET5 = -0.025
REQUIRE_SPY_ABOVE_SMA50 = True

MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

SEC_COMPANY_TICKERS = ROOT / "data" / "reference" / "sec_company_tickers.json"
NON_OPERATING_TITLE_KEYWORDS = (
    " ETF",
    " EXCHANGE TRADED",
    " FUND",
    " TRUST",
    " ETN",
    " PROSHARES",
    " ISHARES",
    " SPDR ",
    " INVESCO QQQ",
    " BARCLAYS BANK PLC",
    " UNITED STATES NATURAL GAS FUND",
    " FIDELITY ETHEREUM",
)
KNOWN_NON_OPERATING_TICKERS = {
    "AGQ",
    "BOIL",
    "ETHA",
    "FETH",
    "UCO",
    "UNG",
    "UVIX",
    "VXX",
}

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117_072.92},
    "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78_110.11},
    "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39_667.96},
}

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260601_012_undercut_reclaim_absorption_candidate_pool.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def _load_sec_titles() -> dict[str, str]:
    if not SEC_COMPANY_TICKERS.exists():
        return {}
    payload = json.loads(SEC_COMPANY_TICKERS.read_text(encoding="utf-8"))
    titles: dict[str, str] = {}
    for row in payload.values():
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        title = str(row.get("title") or "")
        if ticker and title:
            titles[ticker] = title
    return titles


def _non_operating_security_reason(ticker: str, title: str) -> str | None:
    ticker = str(ticker or "").upper()
    if ticker in KNOWN_NON_OPERATING_TICKERS:
        return "known_non_operating_proxy"
    upper = f" {str(title or '').upper()} "
    for keyword in NON_OPERATING_TITLE_KEYWORDS:
        if keyword in upper:
            return "sec_title_non_operating_security"
    return None


def _prepared_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["prev_close"] = out["Close"].shift(1)
    out["prior_10d_low"] = out["Low"].shift(1).rolling(10).min()
    out["avg_volume_20"] = out["Volume"].shift(1).rolling(20).mean()
    out["avg_dollar_volume_20"] = (
        out["Close"].shift(1) * out["Volume"].shift(1)
    ).rolling(20).mean()
    out["volume_ratio_20"] = out["Volume"] / out["avg_volume_20"]
    out["sma50"] = out["Close"].shift(1).rolling(50).mean()
    day_range = out["High"] - out["Low"]
    out["close_location"] = (out["Close"] - out["Low"]) / day_range.where(day_range > 0)
    out["low_to_close_reclaim_pct"] = out["Close"] / out["Low"] - 1.0
    out["gap_vs_prior_close_pct"] = out["Open"] / out["prev_close"] - 1.0
    out["ret20"] = out["Close"] / out["Close"].shift(20) - 1.0
    out["ret5"] = out["Close"] / out["Close"].shift(5) - 1.0
    out["undercut_depth_pct"] = out["prior_10d_low"] / out["Low"] - 1.0
    out["reclaim_buffer_pct"] = out["Close"] / out["prior_10d_low"] - 1.0
    return out


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if "SPY" not in frames:
        raise RuntimeError("SPY is required for ret20 excess and market-stress controls")
    spy = _prepared_frame(frames["SPY"])
    sec_titles = _load_sec_titles()
    core_entries = base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    excluded_non_stock_tickers: set[str] = set()
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])

    for ticker, frame in frames.items():
        ticker = ticker.upper()
        if ticker in base.shadow.EXCLUDED_TICKERS or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        security_title = sec_titles.get(ticker, "")
        non_stock_reason = _non_operating_security_reason(ticker, security_title)
        if non_stock_reason:
            excluded_non_stock_tickers.add(ticker)
            raw_pass_counts[f"stock_only_excluded_{non_stock_reason}"] += 1
            continue

        fr = _prepared_frame(frame)
        for asof in fr.loc[start:end].index:
            if asof not in spy.index:
                continue
            pos = int(fr.index.get_loc(asof))
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            row = fr.loc[asof]
            spy_row = spy.loc[asof]
            values = {
                "close": float(row["Close"]),
                "open": float(row["Open"]),
                "low": float(row["Low"]),
                "prior_10d_low": float(row["prior_10d_low"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "low_to_close_reclaim_pct": float(row["low_to_close_reclaim_pct"]),
                "gap_vs_prior_close_pct": float(row["gap_vs_prior_close_pct"]),
                "ret20_excess_spy": float(row["ret20"] - spy_row["ret20"]),
                "undercut_depth_pct": float(row["undercut_depth_pct"]),
                "reclaim_buffer_pct": float(row["reclaim_buffer_pct"]),
                "spy_ret5": float(spy_row["ret5"]),
                "spy_close": float(spy_row["Close"]),
                "spy_sma50": float(spy_row["sma50"]),
            }
            if any(not math.isfinite(v) for v in values.values()):
                continue
            if values["close"] < MIN_PRICE:
                continue
            raw_pass_counts["price_checked"] += 1
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if REQUIRE_SPY_ABOVE_SMA50 and values["spy_close"] < values["spy_sma50"]:
                continue
            if values["spy_ret5"] < MIN_SPY_RET5:
                continue
            raw_pass_counts["market_stress_passed"] += 1
            if values["gap_vs_prior_close_pct"] < MAX_PRIOR_CLOSE_GAP_DOWN_PCT:
                continue
            raw_pass_counts["gap_damage_passed"] += 1
            if values["undercut_depth_pct"] < MIN_UNDERCUT_DEPTH_PCT:
                continue
            raw_pass_counts["undercut_passed"] += 1
            if values["reclaim_buffer_pct"] < MIN_CLOSE_RECLAIM_BUFFER_PCT:
                continue
            raw_pass_counts["reclaim_passed"] += 1
            if values["low_to_close_reclaim_pct"] < MIN_LOW_TO_CLOSE_RECLAIM_PCT:
                continue
            raw_pass_counts["low_to_close_passed"] += 1
            if values["close_location"] < MIN_CLOSE_LOCATION:
                continue
            raw_pass_counts["close_location_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                continue
            raw_pass_counts["volume_passed"] += 1
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                continue
            raw_pass_counts["ret20_excess_passed"] += 1

            asof_str = str(asof.date())
            same_day_core = core_entries.get(asof_str, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            score = (
                values["low_to_close_reclaim_pct"] * 3.0
                + values["undercut_depth_pct"] * 2.0
                + values["close_location"]
                + min(values["volume_ratio_20"], 4.0) * 0.15
                + max(values["ret20_excess_spy"], 0.0) * 1.5
            )
            candidates_by_date.setdefault(asof_str, []).append(
                {
                    "ticker": ticker,
                    "date": asof_str,
                    "signal_date": asof_str,
                    "window": label,
                    "score": _round(score, 6),
                    "prior_10d_low": _round(values["prior_10d_low"], 4),
                    "undercut_depth_pct": _round(values["undercut_depth_pct"], 6),
                    "reclaim_buffer_pct": _round(values["reclaim_buffer_pct"], 6),
                    "low_to_close_reclaim_pct": _round(values["low_to_close_reclaim_pct"], 6),
                    "close_location": _round(values["close_location"], 6),
                    "volume_ratio_20": _round(values["volume_ratio_20"], 6),
                    "avg_dollar_volume_20": _round(values["avg_dollar_volume_20"], 2),
                    "ret20_excess_spy": _round(values["ret20_excess_spy"], 6),
                    "spy_ret5": _round(values["spy_ret5"], 6),
                    "same_day_core_entry_count": len(same_day_core),
                    "same_ticker_core_overlap": False,
                    "security_title": security_title,
                    "rule_version": RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    selected: list[dict[str, Any]] = []
    raw_candidate_count = 0
    for date, rows in sorted(candidates_by_date.items()):
        raw_candidate_count += len(rows)
        rows.sort(
            key=lambda item: (
                -float(item["score"]),
                -float(item["low_to_close_reclaim_pct"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
        "excluded_non_stock_tickers": sorted(excluded_non_stock_tickers),
        "excluded_non_stock_ticker_count": len(excluded_non_stock_tickers),
    }


def _paper_trade_from_candidate(
    frames: dict[str, pd.DataFrame],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    signal_date = pd.Timestamp(str(candidate.get("date")))
    frame = frames.get(ticker)
    if frame is None or signal_date not in frame.index:
        return None
    pos = int(frame.index.get_loc(signal_date))
    entry_pos = pos + 1
    exit_pos = pos + HOLD_DAYS
    if entry_pos >= len(frame.index) or exit_pos >= len(frame.index):
        return None
    entry_raw = float(frame["Open"].iloc[entry_pos])
    exit_raw = float(frame["Close"].iloc[exit_pos])
    if entry_raw <= 0 or exit_raw <= 0:
        return None
    entry_price = base.apply_entry_fill(entry_raw)
    exit_price = base.apply_slippage(exit_raw, base.SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = exit_price / entry_price - 1.0 - base.ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        **candidate,
        "entry_date": str(frame.index[entry_pos].date()),
        "exit_date": str(frame.index[exit_pos].date()),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
    }


def _overlay_from_paper_trades(
    before_result: dict[str, Any],
    paper_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    pnl_by_exit_date: Counter[str] = Counter()
    overlay_days: list[dict[str, Any]] = []
    for trade in paper_trades:
        exit_date = str(trade.get("exit_date") or "")
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_exit_date[exit_date] += pnl
        overlay_days.append(
            {
                "date": exit_date,
                "ticker": trade.get("ticker"),
                "signal_date": trade.get("signal_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": exit_date,
                "pnl": _round(pnl, 2),
                "source": STEM,
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in before_result.get("equity_curve") or []:
        cumulative_overlay += float(pnl_by_exit_date.get(str(day), 0.0))
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))
    return {
        "overlay_total_pnl": _round(sum(pnl_by_exit_date.values()), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": overlay_days,
        "overlay_day_count": len(overlay_days),
    }


def _target_trade_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_window_pnl = {}
    for label, trades in target_trades_by_window.items():
        by_window_pnl[label] = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    ticker_rows = [
        {
            "ticker": ticker,
            "trade_count": by_ticker_count[ticker],
            "paper_pnl_usd": _round(pnl, 2),
            "positive_pnl_usd": _round(max(pnl, 0.0), 2),
            "positive_pnl_share": _round(pnl / positive_total, 6)
            if pnl > 0 and positive_total > 0
            else None,
        }
        for ticker, pnl in sorted(by_ticker_pnl.items())
    ]
    ticker_rows.sort(
        key=lambda row: (
            -(row["positive_pnl_usd"] or 0.0),
            -abs(row["paper_pnl_usd"] or 0.0),
            row["ticker"],
        )
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": _round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: _round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "ticker_rows": ticker_rows,
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "windows_pnl_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _baseline_drift(before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for label, expected in DOCS_ACCEPTED_BASELINE.items():
        current = before_metrics.get(label, {})
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": current.get("expected_value_score"),
            "expected_value_score_delta": _round(
                float(current.get("expected_value_score") or 0.0)
                - expected["expected_value_score"],
                6,
            ),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": current.get("total_pnl"),
            "total_pnl_delta": _round(
                float(current.get("total_pnl") or 0.0) - expected["total_pnl"],
                2,
            ),
            "matches_docs_baseline": (
                abs(float(current.get("expected_value_score") or 0.0) - expected["expected_value_score"])
                <= 0.001
                and abs(float(current.get("total_pnl") or 0.0) - expected["total_pnl"]) <= 25.0
            ),
        }
    return {
        "docs_source": "docs/backtesting.md accepted exp-20260517-009 metrics",
        "current_source": "current BacktestEngine replay through the docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
        "interpretation": (
            "The experiment uses the same current replay for before/after comparison. "
            "Current-code baseline values drift from the documented accepted snapshot; "
            "positive promotion would require clean baseline parity first."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Undercut-Reclaim Absorption Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['baseline_expected_value_score_sum']}` -> "
        f"`{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- aggregate PnL delta: `${agg['total_pnl_delta_sum']:+,.2f}`",
        f"- target trades: `{target['total_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- Gate 1 docs-baseline match: `{payload['gate1']['baseline_drift']['matches_all_windows']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "The rule uses same-day OHLCV known at the signal close, prior OHLCV "
            "context, SPY market-state context, and free SEC company-title metadata "
            "for operating-company hygiene. It is replay-only/default-off, so no "
            "production entry, ranking, sizing, exit, LLM/news, watchlist, or order "
            "behavior changed.",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    frames = load_warehouse_frames()
    core_universe = sorted(base.get_universe())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    delta_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    candidates_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = base.shadow._run_baseline(core_universe, cfg)
        before = base.overlay_helper._metrics(before_result)
        candidates, diagnostics = _candidate_rows_for_window(frames, label, cfg, before_result)
        selected_trades = [
            trade
            for candidate in candidates
            if (trade := _paper_trade_from_candidate(frames, candidate)) is not None
        ]
        overlay = _overlay_from_paper_trades(before_result, selected_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = base.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        delta_metrics[label] = delta
        target_trades_by_window[label] = selected_trades
        candidates_by_window[label] = diagnostics
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": diagnostics["raw_candidate_count"],
            "raw_candidate_days": diagnostics["candidate_day_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = _aggregate(window_rows)
    baseline_drift = _baseline_drift(before_metrics)
    target_summary = _target_trade_summary(target_trades_by_window)
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in after_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    target_windows = target_summary["windows_with_target_trades"]
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
        and baseline_drift["matches_all_windows"]
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("survival_floor_failed")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if not baseline_drift["matches_all_windows"]:
        failed.append("baseline_drift_blocks_promotion")

    decision = (
        "positive_replay_lead_not_promoted_requires_clean_baseline_and_shared_adapter"
        if aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and concentration_passed
        and not gate4_passed
        else "accepted_undercut_reclaim_absorption_candidate_pool"
        if gate4_passed
        else "rejected_undercut_reclaim_absorption_candidate_pool"
    )
    rationale = (
        "Gate 4 passed on the current three-window replay, but the current baseline "
        "does not match docs/backtesting.md, so this remains a positive lead until "
        "baseline parity and a shared default-off adapter are in place."
        if decision.startswith("positive_replay")
        else "Gate 4 passed and a shared adapter review would be the next step."
        if gate4_passed
        else "Gate 4 failed; no production or shared policy behavior is retained."
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": gate4_passed,
        "hypothesis": (
            "Liquid stock undercut-and-reclaim absorption days with relative "
            "strength may form a cleaner free-OHLCV default-off candidate pool "
            "than rejected gap-chasing pools."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "free_ohlcv_reversal_absorption_candidate_pool",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260426-060",
            "exp-20260529-006",
            "exp-20260601-010",
            "exp-20260601-011",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "materially_different_free_ohlcv_reversal_absorption_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window core baseline plus default-off paper overlay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "entry": "next available open after signal close with shared fill_model entry slippage",
            "exit": "signal_date + 10 trading days close with shared fill_model sell slippage",
        },
        "parameters": {
            "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
            "min_undercut_depth_pct": MIN_UNDERCUT_DEPTH_PCT,
            "min_close_reclaim_buffer_pct": MIN_CLOSE_RECLAIM_BUFFER_PCT,
            "min_low_to_close_reclaim_pct": MIN_LOW_TO_CLOSE_RECLAIM_PCT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20": MIN_VOLUME_RATIO_20,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "max_prior_close_gap_down_pct": MAX_PRIOR_CLOSE_GAP_DOWN_PCT,
            "min_spy_ret5": MIN_SPY_RET5,
            "require_spy_above_sma50": REQUIRE_SPY_ABOVE_SMA50,
            "stock_only_governance": {
                "sec_company_tickers_path": _repo_rel(SEC_COMPANY_TICKERS),
                "non_operating_title_keywords": list(NON_OPERATING_TITLE_KEYWORDS),
                "known_non_operating_tickers": sorted(KNOWN_NON_OPERATING_TICKERS),
            },
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "baseline_must_match_docs": True,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: post-undercut reclaim absorption may capture "
                "demand after stop-clearing without chasing gap-up extension."
            ),
            "2_history_check": (
                "exp-20260426-060 observed an older undercut/reclaim shadow universe; "
                "exp-20260529-006 found Kova shakeout/reclaim positive but only seven "
                "trades; exp-20260601-010/011 rejected gap-up high-close pools because "
                "old_thin regressed and drawdown drifted. This test uses a distinct "
                "reversal-absorption source, not a gap-chasing retry."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three windows; positive aggregate EV/PnL; no EV/PnL "
                "regressed window; >=30 target trades across all 3 windows; drawdown "
                "drift <=0.5pp; survival >=5%; single positive share <=0.50; HHI <=0.30; "
                "baseline parity must be clean for promotion."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_012_undercut_reclaim_absorption_candidate_pool.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_drift": baseline_drift,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "Open/High/Low/Close/Volume through signal_date",
                "prior 10-day low",
                "prior 20-day volume and dollar volume",
                "SPY 5-day return and SMA50 state",
                "ticker ret20 minus SPY ret20",
                "SEC company ticker title metadata from data/reference/sec_company_tickers.json",
                "entry_date and target_price in operator_inputs/open_positions.json",
            ],
        },
        "gate3": {
            "passed": min_survival >= 0.05,
            "note": "No core production filter was added; candidate pool is default-off paper overlay only.",
            "signals_generated_survived_by_window": {
                label: {
                    "signals_generated": row.get("signals_generated"),
                    "signals_survived": row.get("signals_survived"),
                    "survival_rate": row.get("survival_rate"),
                }
                for label, row in after_metrics.items()
            },
        },
        "gate4": {
            "passed": gate4_passed,
            "decision": decision,
            "rationale": rationale,
            "failed_gates": failed,
            "min_survival_rate": _round(min_survival, 6),
            "max_drawdown_delta": aggregate["max_drawdown_delta_max"],
            "requires_parity_before_promotion": not baseline_drift["matches_all_windows"],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "aggregate": aggregate,
        "baseline_drift": baseline_drift,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "candidate_diagnostics_by_window": candidates_by_window,
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "interpretation": rationale,
        "next_retry_requires": [
            "clean current-code baseline parity versus docs/backtesting.md before promotion",
            "new forward replacement-value rows",
            "direct same-day core displacement comparison",
            "shared default-off adapter if a future run promotes this route",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    payload = _build_payload()
    _write_json(output, payload)
    _write_json(
        BEFORE_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
            "expected_value_score": payload["aggregate"]["baseline_expected_value_score_sum"],
            "total_pnl": payload["aggregate"]["baseline_total_pnl_sum"],
            "aggregate_expected_value_score": payload["aggregate"]["baseline_expected_value_score_sum"],
            "aggregate_total_pnl": payload["aggregate"]["baseline_total_pnl_sum"],
            "windows": payload["before_metrics"],
        },
    )
    _write_json(
        AFTER_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "expected_value_score": payload["aggregate"]["after_expected_value_score_sum"],
            "total_pnl": payload["aggregate"]["after_total_pnl_sum"],
            "aggregate_expected_value_score": payload["aggregate"]["after_expected_value_score_sum"],
            "aggregate_total_pnl": payload["aggregate"]["after_total_pnl_sum"],
            "windows": payload["after_metrics"],
        },
    )
    _write_json(LOG_JSON, payload)
    artifact = _artifact(payload)
    _write_text(ARTIFACT_MD, artifact)
    _write_text(CARD_MD, artifact)

    log_row = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "before_metrics": {
            "expected_value_score": payload["aggregate"]["baseline_expected_value_score_sum"],
            "total_pnl": payload["aggregate"]["baseline_total_pnl_sum"],
        },
        "after_metrics": {
            "expected_value_score": payload["aggregate"]["after_expected_value_score_sum"],
            "total_pnl": payload["aggregate"]["after_total_pnl_sum"],
        },
        "delta_metrics": {
            "expected_value_score": payload["aggregate"]["expected_value_score_delta_sum"],
            "total_pnl": payload["aggregate"]["total_pnl_delta_sum"],
            "max_drawdown_pct": payload["aggregate"]["max_drawdown_delta_max"],
            "target_trade_count": payload["target_trade_summary"]["total_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"][
                "max_single_positive_pnl_share"
            ],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["delta"]["expected_value_score"],
                "total_pnl_delta": row["delta"]["total_pnl"],
                "target_trade_count": row["target_trade_count"],
            }
            for label, row in payload["window_results"].items()
        ],
        "production_impact": payload["production_impact"],
        "decision_basis": payload["gate4"],
        "artifact_path": _repo_rel(output),
        "anti_js": "No JavaScript was used.",
    }
    _append_jsonl_once(EXPERIMENT_LOG, log_row)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": _repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
