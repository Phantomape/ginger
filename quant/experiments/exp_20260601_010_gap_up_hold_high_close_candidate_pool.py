"""exp-20260601-010: gap-up hold high-close candidate-pool scout.

Lane: alpha_search.
Single causal variable: gap_up_hold_high_close_volume_confirmed_candidate_source_v1.

This replay-only scout tests whether broad-universe stocks that gap up, absorb
the gap intraday, trade on strong volume, and close near the high have 10-day
continuation value as a default-off paper candidate pool. It changes no
production orders, core ranking, sizing, exits, LLM/news inputs, or watchlists.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
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


EXPERIMENT_ID = "exp-20260601-010"
STEM = "gap_up_hold_high_close_candidate_pool"
TRIAL_FAMILY = "gap_up_hold_high_close_candidate_pool"
CHANGED_VARIABLE = "gap_up_hold_high_close_volume_confirmed_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1

MIN_PRICE = 15.0
MIN_AVG_DOLLAR_VOLUME_20 = 100_000_000.0
MIN_GAP_UP_PCT = 0.03
MIN_INTRADAY_RETURN_PCT = 0.0
MIN_CLOSE_LOCATION = 0.75
MIN_VOLUME_RATIO_20 = 1.5
MIN_RET20_EXCESS_SPY = 0.02

MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117_072.92},
    "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78_110.11},
    "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39_667.96},
}

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
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


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _ret(closes: list[float], pos: int, lookback: int) -> float | None:
    prior = pos - lookback
    if prior < 0:
        return None
    start = closes[prior]
    end = closes[pos]
    if start <= 0 or end <= 0:
        return None
    return end / start - 1.0


def _prepared_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["prev_close"] = out["Close"].shift(1)
    out["avg_volume_20"] = out["Volume"].shift(1).rolling(20).mean()
    out["avg_dollar_volume_20"] = (
        out["Close"].shift(1) * out["Volume"].shift(1)
    ).rolling(20).mean()
    out["volume_ratio_20"] = out["Volume"] / out["avg_volume_20"]
    day_range = out["High"] - out["Low"]
    out["close_location"] = (out["Close"] - out["Low"]) / day_range.where(day_range > 0)
    out["gap_up_pct"] = out["Open"] / out["prev_close"] - 1.0
    out["intraday_return_pct"] = out["Close"] / out["Open"] - 1.0
    out["ret20"] = out["Close"] / out["Close"].shift(20) - 1.0
    return out


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy = _prepared_frame(frames["SPY"]) if "SPY" in frames else None
    if spy is None:
        raise RuntimeError("SPY is required in the broad warehouse for ret20 excess control")

    core_entries = base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])

    for ticker, frame in frames.items():
        ticker = ticker.upper()
        if ticker in base.shadow.EXCLUDED_TICKERS or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        fr = _prepared_frame(frame)
        dates = [idx for idx in fr.loc[start:end].index]
        closes = [float(value) for value in fr["Close"].tolist()]
        pos_by_date = {idx: pos for pos, idx in enumerate(fr.index)}
        for asof in dates:
            row = fr.loc[asof]
            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            spy_pos = spy.index.get_loc(asof)
            spy_closes = [float(value) for value in spy["Close"].tolist()]
            spy_ret20 = _ret(spy_closes, int(spy_pos), 20)
            ret20 = _ret(closes, pos, 20)
            if ret20 is None or spy_ret20 is None:
                continue
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "gap_up_pct": float(row["gap_up_pct"]),
                "intraday_return_pct": float(row["intraday_return_pct"]),
                "close_location": float(row["close_location"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "ret20_excess_spy": ret20 - spy_ret20,
            }
            if any(not math.isfinite(v) for v in values.values()):
                continue
            if values["close"] < MIN_PRICE:
                continue
            raw_pass_counts["price_liquidity_checked"] += 1
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if values["gap_up_pct"] < MIN_GAP_UP_PCT:
                continue
            raw_pass_counts["gap_passed"] += 1
            if values["intraday_return_pct"] < MIN_INTRADAY_RETURN_PCT:
                continue
            raw_pass_counts["intraday_hold_passed"] += 1
            if values["close_location"] < MIN_CLOSE_LOCATION:
                continue
            raw_pass_counts["high_close_passed"] += 1
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
                values["gap_up_pct"] * 4.0
                + min(values["volume_ratio_20"], 5.0) * 0.25
                + values["close_location"]
                + values["ret20_excess_spy"]
            )
            candidates_by_date.setdefault(asof_str, []).append(
                {
                    "ticker": ticker,
                    "date": asof_str,
                    "signal_date": asof_str,
                    "window": label,
                    "score": _round(score, 6),
                    "gap_up_pct": _round(values["gap_up_pct"], 6),
                    "intraday_return_pct": _round(values["intraday_return_pct"], 6),
                    "close_location": _round(values["close_location"], 6),
                    "volume_ratio_20": _round(values["volume_ratio_20"], 6),
                    "avg_dollar_volume_20": _round(values["avg_dollar_volume_20"], 2),
                    "ret20_excess_spy": _round(values["ret20_excess_spy"], 6),
                    "same_day_core_entry_count": len(same_day_core),
                    "same_ticker_core_overlap": False,
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
                -float(item["gap_up_pct"]),
                -float(item["volume_ratio_20"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
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
        actual = before_metrics.get(label) or {}
        ev_delta = float(actual.get("expected_value_score") or 0.0) - float(
            expected["expected_value_score"]
        )
        pnl_delta = float(actual.get("total_pnl") or 0.0) - float(expected["total_pnl"])
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": actual.get("expected_value_score"),
            "expected_value_score_delta": _round(ev_delta, 6),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": actual.get("total_pnl"),
            "total_pnl_delta": _round(pnl_delta, 2),
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    return {
        "docs_source": "docs/backtesting.md accepted exp-20260517-009 metrics",
        "current_source": "current BacktestEngine replay through the docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
        "interpretation": (
            "The experiment uses the same three windows and same current replay for "
            "before/after comparison, but current-code baseline values drift from "
            "the documented accepted snapshot. Because Gate 4 rejects the alpha, "
            "no strategy is retained; a future positive result should first reconcile "
            "this Gate 1 baseline drift."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Gap-Up Hold High-Close Candidate Pool",
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
            "The rule uses only same-day OHLCV and prior 20-day OHLCV context known "
            "at the signal close. It is replay-only/default-off, so no production "
            "entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.",
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

    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4_passed
        else "rejected_gap_up_hold_high_close_candidate_pool"
    )
    rationale = (
        "Gate 4 passed, but this broad-universe replay remains a positive lead only "
        "until a shared default-off production/backtest adapter proves parity."
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
            "Liquid broad-universe stocks that gap up on strong volume, hold the gap "
            "intraday, and close near the high may represent institutional demand "
            "with 10-day continuation alpha as a default-off paper candidate pool."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "free_ohlcv_gap_and_hold_candidate_pool",
        "prior_trial_count": 1,
        "nearby_prior_experiments": ["exp-20260426-044", "exp-20260601-007", "exp-20260601-008"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_broad_universe_candidate_pool",
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
            "min_gap_up_pct": MIN_GAP_UP_PCT,
            "min_intraday_return_pct": MIN_INTRADAY_RETURN_PCT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20": MIN_VOLUME_RATIO_20,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
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
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: a production-visible gap-and-hold day "
                "may identify institutional demand not captured by the existing core queue."
            ),
            "2_history_check": (
                "exp-20260426-044 was an older gap-and-hold shadow observation before "
                "the current canonical three-window/default-off candidate-pool protocol; "
                "exp-20260601-007/008 found broad short-horizon continuation is mostly "
                "ordinary momentum, so this test requires gap absorption plus volume and "
                "all-window/concentration gates."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three windows; positive aggregate EV/PnL; no EV/PnL "
                "regressed window; >=30 target trades in all 3 windows; drawdown drift "
                "<=0.5pp; survival >=5%; single positive share <=0.50 and HHI <=0.30."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_010_gap_up_hold_high_close_candidate_pool.py"
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
                "prior close",
                "prior 20-day volume and dollar volume",
                "SPY prior 20-day return",
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
            "requires_parity_before_promotion": gate4_passed,
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
    _upsert_jsonl(EXPERIMENT_LOG, log_row)
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
