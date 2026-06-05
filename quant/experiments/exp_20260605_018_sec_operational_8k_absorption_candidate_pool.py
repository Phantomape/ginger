"""exp-20260605-018: SEC operational 8-K quiet absorption candidate pool.

This alpha search tests one replay-only/default-off paper candidate source:
operational 8-K items (`1.01`, `7.01`, `8.01`) that close strongly on the
first usable trading day while volume stays quiet. To preserve
production/backtest parity, the paper entry is delayed until the next open
after that close is known.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402


EXP_ID = "exp-20260605-018"
STEM = "sec_operational_8k_absorption_candidate_pool"
TRIAL_FAMILY = "sec_operational_8k_absorption_candidate_pool"
TRIAL_VARIANT_ID = "sec_operational_8k_absorption_top1_delayed_entry_v1"
CHANGED_VARIABLE = "sec_operational_8k_quiet_absorption_delayed_entry_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_018_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

INITIAL_CAPITAL = 100_000.0
PAPER_NOTIONAL = 4_000.0
HOLD_DAYS = 10
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

INCLUDED_ITEM_CODES = frozenset({"1.01", "7.01", "8.01"})
EXCLUDED_ITEM_PREFIXES = ("2.02", "2.03", "3.02", "4.01", "5.")
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MAX_SIGNAL_VOLUME_RATIO_20D = 1.25
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MIN_SIGNAL_DAY_RETURN = 0.0
MIN_RET20_EXCESS_SPY = 0.0
MAX_PAPER_TRADES_PER_ENTRY_DAY = 1

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. It uses only historical "
        "PIT-safe SEC filing feature rows, first usable trading-day OHLCV "
        "available after the close, and a delayed next-open paper entry. A "
        "positive result would still require a separate shared default-off SEC "
        "filing-feature adapter and parity tests before any report queue, "
        "candidate priority, or order surface could change."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _configure_overlay_module() -> None:
    overlay.WINDOWS = WINDOWS
    overlay.INITIAL_CAPITAL = INITIAL_CAPITAL
    overlay.EVENT_NOTIONAL = PAPER_NOTIONAL
    overlay.HOLD_DAYS = HOLD_DAYS


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _item_codes(raw: Any) -> set[str]:
    return {part.strip() for part in str(raw or "").replace(";", ",").split(",") if part.strip()}


def _frame_pos_on_or_after(frame: pd.DataFrame, day: str) -> int | None:
    pos = int(frame.index.searchsorted(pd.Timestamp(day), side="left"))
    return pos if pos < len(frame) else None


def _ret(frame: pd.DataFrame, pos: int, lookback: int) -> float | None:
    prior = pos - lookback
    if prior < 0:
        return None
    start = _float_or_none(frame["Close"].iloc[prior])
    end = _float_or_none(frame["Close"].iloc[pos])
    if start is None or end is None or start <= 0.0 or end <= 0.0:
        return None
    return end / start - 1.0


def _avg_dollar_volume(frame: pd.DataFrame, pos: int, lookback: int = 20) -> float | None:
    start = pos - lookback + 1
    if start < 0:
        return None
    rows = frame.iloc[start : pos + 1]
    values = rows["Close"].astype(float) * rows["Volume"].astype(float)
    return float(values.mean()) if len(values) == lookback else None


def _volume_ratio(frame: pd.DataFrame, pos: int, lookback: int = 20) -> float | None:
    start = pos - lookback + 1
    if start < 0:
        return None
    avg = float(frame["Volume"].iloc[start : pos + 1].mean())
    current = float(frame["Volume"].iloc[pos])
    return current / avg if avg > 0.0 else None


def _close_location(frame: pd.DataFrame, pos: int) -> float | None:
    high = _float_or_none(frame["High"].iloc[pos])
    low = _float_or_none(frame["Low"].iloc[pos])
    close = _float_or_none(frame["Close"].iloc[pos])
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _price_map_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
    prices: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in frames.items():
        prices[ticker] = [
            {
                "date": str(day.date()),
                "open": float(row["Open"]),
                "close": float(row["Close"]),
            }
            for day, row in frame.iterrows()
        ]
    return prices


def _load_feature_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    source_files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_features_*.jsonl"))
    raw_rows_scanned = 0
    by_window_all: Counter[str] = Counter()
    for path in source_files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw_rows_scanned += 1
                row = json.loads(line)
                usable = str(row.get("usable_trade_date") or "")[:10]
                window = _window_name(usable)
                if window is None:
                    continue
                key = (
                    str(row.get("ticker") or "").upper(),
                    str(row.get("source_accession") or row.get("accession_number") or ""),
                    usable,
                    str(row.get("eight_k_item_type") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                by_window_all[window] += 1
                rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("source_accession") or ""),
        )
    )
    return rows, {
        "source_file_count": len(source_files),
        "raw_rows_scanned": raw_rows_scanned,
        "unique_rows_in_canonical_windows": len(rows),
        "unique_rows_by_window": dict(sorted(by_window_all.items())),
    }


def _candidate_from_feature_row(
    row: dict[str, Any],
    *,
    frames: dict[str, pd.DataFrame],
    spy_frame: pd.DataFrame,
) -> tuple[dict[str, Any] | None, str]:
    ticker = str(row.get("ticker") or "").upper()
    usable = str(row.get("usable_trade_date") or "")[:10]
    window = _window_name(usable)
    if not ticker or not usable or window is None:
        return None, "outside_window_or_missing_ticker"
    if "8-K" not in str(row.get("form_type") or "").upper():
        return None, "not_8k"

    codes = _item_codes(row.get("eight_k_item_type"))
    if not codes.intersection(INCLUDED_ITEM_CODES):
        return None, "no_operational_item"
    if any(code.startswith(EXCLUDED_ITEM_PREFIXES) for code in codes):
        return None, "excluded_item"

    frame = frames.get(ticker)
    if frame is None:
        return None, "missing_price_history"
    signal_pos = _frame_pos_on_or_after(frame, usable)
    spy_pos = _frame_pos_on_or_after(spy_frame, usable)
    if signal_pos is None or spy_pos is None:
        return None, "missing_signal_day"

    entry_pos = signal_pos + 1
    exit_pos = entry_pos + HOLD_DAYS
    if exit_pos >= len(frame):
        return None, "missing_exit_price"

    signal_date = str(frame.index[signal_pos].date())
    entry_date = str(frame.index[entry_pos].date())
    exit_date = str(frame.index[exit_pos].date())
    if not (WINDOWS[window]["start"] <= entry_date <= WINDOWS[window]["end"]):
        return None, "entry_outside_window"

    signal_close = _float_or_none(frame["Close"].iloc[signal_pos])
    if signal_close is None or signal_close < MIN_PRICE:
        return None, "price_floor"

    adv20 = _avg_dollar_volume(frame, signal_pos)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None, "adv20_floor"

    volume_ratio_20d = _volume_ratio(frame, signal_pos)
    if volume_ratio_20d is None or volume_ratio_20d > MAX_SIGNAL_VOLUME_RATIO_20D:
        return None, "not_quiet_volume"

    close_location = _close_location(frame, signal_pos)
    if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None, "weak_close_location"

    signal_day_return = _ret(frame, signal_pos, 1)
    if signal_day_return is None or signal_day_return < MIN_SIGNAL_DAY_RETURN:
        return None, "negative_signal_day_return"

    ret20 = _ret(frame, signal_pos, 20)
    spy_ret20 = _ret(spy_frame, spy_pos, 20)
    if ret20 is None or spy_ret20 is None or ret20 - spy_ret20 < MIN_RET20_EXCESS_SPY:
        return None, "weak_ret20_excess_spy"

    entry_open = _float_or_none(frame["Open"].iloc[entry_pos])
    exit_close = _float_or_none(frame["Close"].iloc[exit_pos])
    if entry_open is None or exit_close is None or entry_open <= 0.0 or exit_close <= 0.0:
        return None, "missing_open_or_close"

    gross_return = exit_close / entry_open - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    item_score = (
        (2.0 if "1.01" in codes else 0.0)
        + (1.0 if "8.01" in codes else 0.0)
        + (0.5 if "7.01" in codes else 0.0)
    )
    candidate_score = (
        item_score
        + close_location
        + 3.0 * min(max(ret20 - spy_ret20, 0.0), 0.30)
        + (MAX_SIGNAL_VOLUME_RATIO_20D - volume_ratio_20d)
    )
    return {
        "ticker": ticker,
        "usable_trade_date": usable,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "window": window,
        "form_type": row.get("form_type"),
        "eight_k_item_type": row.get("eight_k_item_type"),
        "source_accession": row.get("source_accession"),
        "event_date": str(row.get("event_date") or "")[:10],
        "filing_date": str(row.get("filing_date") or "")[:10],
        "accepted_datetime": row.get("accepted_datetime"),
        "status": "price_ready",
        "strategy": STEM,
        "rule_version": RULE_VERSION,
        "included_item_codes": sorted(codes.intersection(INCLUDED_ITEM_CODES)),
        "signal_close": round(signal_close, 6),
        "signal_day_return": round(signal_day_return, 6),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20 - spy_ret20, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "close_location": round(close_location, 6),
        "candidate_selection_score": round(candidate_score, 6),
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "gross_return_pct": round(gross_return * 100.0, 6),
        "net_return_pct": round(net_return * 100.0, 6),
        "notional": PAPER_NOTIONAL,
        "shares": PAPER_NOTIONAL / entry_open,
        "pnl": round(PAPER_NOTIONAL * net_return, 2),
        "known_at": "usable_trade_date_close_before_next_open_delayed_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }, "candidate_ready"


def _generate_candidates(frames: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, source_audit = _load_feature_rows()
    spy_frame = frames["SPY"]
    candidates: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    source_rows_by_window: Counter[str] = Counter()
    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        window = _window_name(usable)
        if window:
            source_rows_by_window[window] += 1
        candidate, reason = _candidate_from_feature_row(row, frames=frames, spy_frame=spy_frame)
        if candidate is None:
            rejects[reason] += 1
            continue
        candidates.append(candidate)
    candidates.sort(
        key=lambda row: (
            row["entry_date"],
            -float(row.get("candidate_selection_score") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    return candidates, {
        **source_audit,
        "candidate_count_before_top1": len(candidates),
        "candidate_count_before_top1_by_window": dict(
            sorted(Counter(row["window"] for row in candidates).items())
        ),
        "candidate_ticker_count_before_top1": len({row["ticker"] for row in candidates}),
        "reject_reasons": dict(sorted(rejects.items())),
        "source_rows_by_window": dict(sorted(source_rows_by_window.items())),
    }


def _select_top1_per_entry_day(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[str(row.get("entry_date") or "")].append(row)

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry_date, rows in sorted(grouped.items()):
        rows.sort(
            key=lambda row: (
                -float(row.get("candidate_selection_score") or 0.0),
                str(row.get("ticker") or ""),
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_ENTRY_DAY])
        for row in rows[MAX_PAPER_TRADES_PER_ENTRY_DAY:]:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "entry_date": entry_date,
                    "usable_trade_date": row.get("usable_trade_date"),
                    "window": row.get("window"),
                    "reason": "max_paper_trades_per_entry_day_full",
                    "candidate_selection_score": row.get("candidate_selection_score"),
                }
            )
    return selected, skipped


def _aggregate_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in rows.values()),
            4,
        ),
        "strategy_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in rows.values()),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in rows.values()),
        "survival_rate_min": min(float(row.get("survival_rate") or 0.0) for row in rows.values()),
        "max_drawdown_pct_max": max(float(row.get("max_drawdown_pct") or 0.0) for row in rows.values()),
    }


def _compare_aggregate(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_ev = float(before.get("expected_value_score") or 0.0)
    after_ev = float(after.get("expected_value_score") or 0.0)
    before_pnl = float(before.get("strategy_total_pnl") or 0.0)
    after_pnl = float(after.get("strategy_total_pnl") or 0.0)
    return {
        "expected_value_score_delta": round(after_ev - before_ev, 4),
        "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
        if before_ev
        else None,
        "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
        "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
        if before_pnl
        else None,
        "trade_count_delta": int(after.get("trade_count") or 0) - int(before.get("trade_count") or 0),
        "survival_rate_min_delta": round(
            float(after.get("survival_rate_min") or 0.0)
            - float(before.get("survival_rate_min") or 0.0),
            6,
        ),
        "max_drawdown_delta": round(
            float(after.get("max_drawdown_pct_max") or 0.0)
            - float(before.get("max_drawdown_pct_max") or 0.0),
            6,
        ),
    }


def _target_summary(selected: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(row["window"] for row in selected)
    positive_by_ticker: Counter[str] = Counter()
    for trade in selected:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl > 0.0:
            positive_by_ticker[str(trade.get("ticker") or "missing")] += pnl
    total_positive = sum(positive_by_ticker.values())
    shares = [value / total_positive for value in positive_by_ticker.values()] if total_positive else []
    return {
        "target_trade_count": len(selected),
        "target_trade_count_by_window": {label: int(by_window.get(label, 0)) for label in WINDOWS},
        "target_trade_pnl_usd": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
        "target_trade_pnl_by_window": {
            label: round(sum(float(row.get("pnl") or 0.0) for row in selected if row["window"] == label), 2)
            for label in WINDOWS
        },
        "positive_pnl_by_ticker": {
            ticker: round(value, 2) for ticker, value in sorted(positive_by_ticker.items())
        },
        "max_single_positive_share": round(max(shares), 6) if shares else 0.0,
        "positive_pnl_hhi": round(sum(share * share for share in shares), 6),
        "target_ticker_count": len({row["ticker"] for row in selected}),
        "top_target_tickers": Counter(row["ticker"] for row in selected).most_common(20),
    }


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_delta = float(aggregate_comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(aggregate_comparison.get("strategy_total_pnl_delta") or 0.0)
    ev_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(float(row["comparison"].get("max_drawdown_delta") or 0.0) for row in results)
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_trade_count = int(target_summary.get("target_trade_count") or 0)
    target_windows = sum(1 for label in WINDOWS if int(target_summary["target_trade_count_by_window"].get(label, 0)) > 0)
    gates = {
        "aggregate_expected_value_positive": ev_delta > 0.0,
        "aggregate_pnl_positive": pnl_delta > 0.0,
        "all_windows_expected_value_improved": len(ev_windows_improved) == len(results),
        "all_windows_pnl_improved": len(pnl_windows_improved) == len(results),
        "target_trade_count_passed": target_trade_count >= MIN_TARGET_TRADES,
        "target_window_count_passed": target_windows >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": (
            float(target_summary["max_single_positive_share"]) <= MAX_SINGLE_POSITIVE_SHARE
            and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
        ),
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_sec_filing_adapter"
        status = "observed_only"
        rationale = (
            "The delayed-entry operational 8-K absorption source improved all "
            "canonical windows and passed sample, drawdown, survival, and "
            "concentration guards. It remains replay-only until a shared "
            "default-off adapter and parity tests are implemented."
        )
    else:
        decision = "rejected_sec_operational_8k_absorption_candidate_pool"
        status = "rejected"
        rationale = (
            "One or more Gate 4 checks failed, so this SEC operational 8-K "
            "absorption candidate source is not retained or promoted."
        )
    return {
        "decision": decision,
        "status": status,
        "passed": passed,
        "rationale": rationale,
        "gates": gates,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": round(max_drawdown_delta, 6),
        "min_survival_rate": round(min_survival_rate, 6),
        "requires_parity_before_promotion": passed,
    }


def _daily_sharpe_from_combined_curve(metrics: dict[str, Any]) -> dict[str, Any]:
    curve = metrics.get("combined_equity_curve") or []
    returns = []
    for (_, prev), (_, curr) in zip(curve, curve[1:]):
        if float(prev) > 0:
            returns.append(float(curr) / float(prev) - 1.0)
    if len(returns) < 2:
        return {"daily_return_mean": None, "daily_return_stdev": None}
    stdev = statistics.stdev(returns)
    return {
        "daily_return_mean": round(sum(returns) / len(returns), 8),
        "daily_return_stdev": round(stdev, 8),
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(lines)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Operational 8-K Absorption Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            (
                "Select PIT-safe SEC 8-K feature rows with operational item "
                "codes 1.01/7.01/8.01, exclude earnings/financing/governance "
                "items, require first usable trading-day close-location >= "
                f"{MIN_SIGNAL_CLOSE_LOCATION}, volume_ratio_20d <= "
                f"{MAX_SIGNAL_VOLUME_RATIO_20D}, nonnegative signal-day return, "
                "and nonnegative 20d excess return versus SPY. Entry is delayed "
                "to the next open after that close is known."
            ),
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_018_sec_operational_8k_absorption_candidate_pool.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    prediction = ticket.get("prediction") or payload.get("prediction") or {}
    actual_success = 1 if payload["gate4"]["passed"] else 0
    if isinstance(prediction, dict):
        prediction.update(
            {
                "actual_success": actual_success,
                "actual_ev_delta": payload["aggregate"]["comparison"]["expected_value_score_delta"],
                "actual_pnl_delta": payload["aggregate"]["comparison"]["strategy_total_pnl_delta"],
                "brier_score": round((float(prediction.get("success_probability") or 0.0) - actual_success) ** 2, 6),
            }
        )
    ticket.update(
        {
            "status": payload["gate4"]["status"],
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "prediction": prediction,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"]["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"]["strategy_total_pnl_delta"],
                "artifact": _repo_rel(ARTIFACT_MD),
                "log": _repo_rel(LOG_JSON),
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        return
    for item in registry.setdefault("experiments", []):
        if isinstance(item, dict) and item.get("experiment_id") == EXP_ID:
            item["status"] = payload["gate4"]["status"]
            item["decision"] = payload["gate4"]["decision"]
            item["updated_at"] = payload["completed_at"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"]["expected_value_score_delta"]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"]["strategy_total_pnl_delta"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = payload.get("prediction") or {}
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "prediction": {
            **prediction,
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round((float(prediction.get("success_probability") or 0.0) - actual_success) ** 2, 6),
        },
        "next_action": payload["next_action"],
        "related_files": [_repo_rel(OUT_JSON), _repo_rel(ARTIFACT_MD), _repo_rel(LOG_JSON)],
    }


def _append_experiment_log(record: dict[str, Any]) -> None:
    compact = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    _configure_overlay_module()
    completed_at = _utc_now()
    universe = get_universe()
    frames = load_warehouse_frames()
    prices = _price_map_from_frames(frames)
    candidates_before_top1, candidate_audit = _generate_candidates(frames)
    selected_candidates, skipped_candidates = _select_top1_per_entry_day(candidates_before_top1)

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    target_details: dict[str, dict[str, Any]] = {}
    core_run_audit: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected = [
            row
            for row in selected_candidates
            if row.get("window") == label
            and window["start"] <= str(row.get("entry_date") or "") <= window["end"]
        ]
        event_curve = overlay._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before = overlay._core_metrics(result)
        after = overlay._combined_metrics(result, event_curve, selected)
        before_metrics[label] = before
        after_metrics[label] = after
        comparison = {
            "expected_value_score_delta": round(
                float(after.get("expected_value_score") or 0.0)
                - float(before.get("expected_value_score") or 0.0),
                4,
            ),
            "strategy_total_pnl_delta": round(
                float(after.get("total_pnl") or 0.0)
                - float(before.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_delta": round(
                float(after.get("max_drawdown_pct") or 0.0)
                - float(before.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
        results.append(
            {
                "label": label,
                "window": window,
                "before": before,
                "after": after,
                "comparison": comparison,
                "target_trade_count": len(selected),
                "target_trade_pnl_usd": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
                "return_diagnostics": _daily_sharpe_from_combined_curve(after),
            }
        )
        target_details[label] = {
            "candidate_count_before_top1": sum(1 for row in candidates_before_top1 if row.get("window") == label),
            "selected_trade_count": len(selected),
            "selected_trades": selected,
            "skipped_candidates": [
                row for row in skipped_candidates if row.get("window") == label
            ][:100],
        }
        core_run_audit[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "signals_generated": result.get("signals_generated"),
            "signals_survived": result.get("signals_survived"),
            "survival_rate": result.get("survival_rate"),
        }

    aggregate_before = _aggregate_metrics(before_metrics)
    aggregate_after = _aggregate_metrics(after_metrics)
    aggregate_comparison = _compare_aggregate(aggregate_before, aggregate_after)
    target_summary = _target_summary(selected_candidates)
    gate4 = _gate4(aggregate_comparison, results, target_summary)
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.10,
        "expected_pnl_delta": 1500.0,
        "main_failure_modes": [
            "old_thin_and_late_strong_regression",
            "operational_8k_rows_are_procedural",
            "single_ticker_or_event_concentration",
            "delayed_entry_loses_reaction_alpha",
        ],
        "confidence_reason": (
            "Historical SEC item-type rows are broad and PIT-safe, but prior "
            "simple SEC event-graph fields were weak and preflight PnL was mixed."
        ),
        "recorded_at": "2026-06-05T11:12:45Z",
    }
    return {
        "experiment_id": EXP_ID,
        "completed_at": completed_at,
        "anti_js": "No JavaScript was used.",
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "preflight": {
            "alpha_hypothesis": (
                "Operational SEC 8-K items whose first usable trading day "
                "closes strong on quiet volume may identify cleaner next-open "
                "default-off paper candidates than raw SEC event fields."
            ),
            "category": "entry_candidate_pool",
            "playbook_alignment": (
                "Uses a free, production-visible SEC feature layer and tests a "
                "candidate-pool source instead of LLM soft-ranking, Companyfacts "
                "peer retunes, FTD/FINRA retunes, post-earnings support stack "
                "retunes, or broad OHLCV-only pattern mining."
            ),
            "nearby_prior_experiments": {
                "exp-20260530-006": "Rejected raw same-family SEC burst count.",
                "exp-20260530-008": "Rejected same-ticker first/follow-on SEC recurrence.",
                "exp-20260530-009": "Rejected same-ticker cross-family SEC transitions.",
                "exp-20260605-017": "Rejected source_credibility_bucket branch because historical field was absent.",
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_criteria": {
                "canonical_windows": list(WINDOWS.keys()),
                "aggregate_expected_value_delta": "> 0",
                "aggregate_pnl_delta": "> 0",
                "per_window_expected_value_delta": "3 of 3 windows > 0",
                "per_window_pnl_delta": "3 of 3 windows > 0",
                "minimum_target_trades": MIN_TARGET_TRADES,
                "minimum_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_drift": MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            },
        },
        "parameters": {
            "feature_glob": "data/non_ohlcv/sec_filing_features_*.jsonl",
            "included_item_codes": sorted(INCLUDED_ITEM_CODES),
            "excluded_item_prefixes": EXCLUDED_ITEM_PREFIXES,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "max_signal_volume_ratio_20d": MAX_SIGNAL_VOLUME_RATIO_20D,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_day_return": MIN_SIGNAL_DAY_RETURN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "entry_policy": "next_open_after_first_usable_trading_day_close",
            "paper_notional": PAPER_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_entry_day": MAX_PAPER_TRADES_PER_ENTRY_DAY,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "initial_capital": INITIAL_CAPITAL,
        },
        "data_availability": candidate_audit,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "results": results,
        "aggregate": {
            "before": aggregate_before,
            "after": aggregate_after,
            "comparison": aggregate_comparison,
        },
        "target_summary": target_summary,
        "gate4": gate4,
        "target_details": target_details,
        "core_run_audit": core_run_audit,
        "prediction": prediction,
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": "LLM soft-ranking data was not used; this is deterministic free SEC/OHLCV data.",
        },
        "next_action": (
            "If positive, build a shared default-off SEC filing-feature adapter "
            "with delayed-entry semantics and parity tests before promotion."
            if gate4["passed"]
            else "Do not retune nearby operational 8-K item/quiet-volume absorption thresholds on this frozen sample; pivot to a different free-data candidate-pool mechanism or forward replacement rows."
        ),
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_json(LOG_JSON, payload)
    _write_artifact(payload)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(ARTIFACT_MD.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {
        "experiment_id": EXP_ID,
        "generated_at": payload["completed_at"],
        "files": [
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(__file__),
        ],
        "production_impact": PRODUCTION_IMPACT,
    }
    _write_json(MANIFEST_JSON, manifest)
    _update_ticket(payload)
    _update_registry(payload)
    _append_experiment_log(_experiment_log_record(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
