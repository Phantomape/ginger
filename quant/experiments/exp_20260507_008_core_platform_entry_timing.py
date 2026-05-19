"""exp-20260507-008: core platform entry timing replay.

Alpha search, replay-only. This experiment tests whether a core platform
cohort seeded by NFLX/APP/META would have benefited from waiting for a small
post-signal pullback instead of buying the next available open.

No production path is changed. The replay only replaces baseline entries that
were already entered for the treatment cohort; skipped delayed entries do not
backfill the freed slot. This keeps the single causal variable on entry timing.
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


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from fill_model import (  # noqa: E402
    SLIPPAGE_BPS_TARGET,
    apply_entry_fill,
    apply_slippage,
    apply_stop_fill,
    apply_target_fill,
)


EXPERIMENT_ID = "exp-20260507-008"
STEM = "core_platform_entry_timing"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
BASELINE_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260507-006.json"

INITIAL_CAPITAL = 100_000.0
ATR_LOOKBACK = 14
SMA_LOOKBACK = 50
PULLBACK_ATR_FRACTION = 0.5
MIN_PULLBACK_PCT = 0.015
MAX_PULLBACK_PCT = 0.04
FORWARD_HORIZONS = (5, 10, 20, 40)
MFE_MAE_HORIZON = 20

TREATMENT_POOL = ("NFLX", "APP", "META", "GOOG", "AMZN", "SPOT", "DIS")
CONTROL_POOL = ("AAPL", "MSFT", "PLTR", "DDOG", "SNOW", "NOW")

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-008/"
                    "entry_candidate_events_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-008/"
                    "entry_candidate_events_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-008/"
                    "entry_candidate_events_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("pullback_limit_3d_0_5atr", {"wait_days": 3}),
        ("pullback_limit_5d_0_5atr", {"wait_days": 5}),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected OHLCV snapshot shape: {snapshot_path}")
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        if not isinstance(rows, list):
            continue
        clean_rows = []
        for row in rows:
            if isinstance(row, dict) and row.get("Date"):
                clean_rows.append(row)
        out[str(ticker).upper()] = sorted(clean_rows, key=lambda row: str(row["Date"]))
    return out


def _load_candidate_payload(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    events = payload.get("candidate_events")
    if not isinstance(events, list):
        raise RuntimeError(f"Missing candidate_events: {path}")
    return payload


def _load_baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_LOG)
    metrics = payload.get("baseline_metrics")
    if not isinstance(metrics, dict):
        raise RuntimeError(f"Missing baseline_metrics: {BASELINE_LOG}")
    return metrics


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


def _open(row: dict[str, Any]) -> float | None:
    return _float(row.get("Open"))


def _high(row: dict[str, Any]) -> float | None:
    return _float(row.get("High"))


def _low(row: dict[str, Any]) -> float | None:
    return _float(row.get("Low"))


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date"))[:10]: idx for idx, row in enumerate(rows)}


def _idx_for_date(rows: list[dict[str, Any]], date_str: str) -> int | None:
    return _date_index(rows).get(str(date_str)[:10])


def _last_idx_on_or_before(rows: list[dict[str, Any]], date_str: str) -> int | None:
    dates = [str(row.get("Date"))[:10] for row in rows]
    target = str(date_str)[:10]
    best = None
    for idx, date_value in enumerate(dates):
        if date_value <= target:
            best = idx
        else:
            break
    return best


def _last_idx_on_or_before_end(rows: list[dict[str, Any]], end: str) -> int:
    idx = _last_idx_on_or_before(rows, end)
    if idx is None:
        return len(rows) - 1
    return idx


def _sma_at_idx(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx + 1 < lookback:
        return None
    closes = [_close(row) for row in rows[idx - lookback + 1 : idx + 1]]
    closes = [value for value in closes if value is not None]
    if len(closes) != lookback:
        return None
    return sum(closes) / len(closes)


def _atr_at_idx(rows: list[dict[str, Any]], idx: int, lookback: int = ATR_LOOKBACK) -> float | None:
    if idx < lookback:
        return None
    true_ranges: list[float] = []
    for i in range(idx - lookback + 1, idx + 1):
        high = _high(rows[i])
        low = _low(rows[i])
        prev_close = _close(rows[i - 1]) if i > 0 else None
        if high is None or low is None or prev_close is None:
            return None
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(true_ranges) / len(true_ranges) if true_ranges else None


def _dist(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "p25": None,
            "p75": None,
            "win_rate": None,
            "best": None,
            "worst": None,
        }
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": _round(sum(clean) / len(clean), 6),
        "median": _round(statistics.median(clean), 6),
        "p25": _round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": _round(ordered[int((len(ordered) - 1) * 0.75)], 6),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "best": _round(max(clean), 6),
        "worst": _round(min(clean), 6),
    }


def _forward_return(
    rows: list[dict[str, Any]],
    date_str: str,
    horizon: int,
    *,
    start_price: float | None = None,
) -> float | None:
    idx = _idx_for_date(rows, date_str)
    if idx is None or idx + horizon >= len(rows):
        return None
    entry = start_price if start_price is not None else _close(rows[idx])
    future = _close(rows[idx + horizon])
    if entry is None or future is None or entry <= 0:
        return None
    return future / entry - 1.0


def _future_extrema(
    rows: list[dict[str, Any]],
    date_str: str,
    horizon: int,
    reference_price: float,
) -> dict[str, Any]:
    idx = _idx_for_date(rows, date_str)
    if idx is None or reference_price <= 0:
        return {
            "mfe_pct": None,
            "mae_pct": None,
            "entry_over_future_low_pct": None,
        }
    end_idx = min(len(rows) - 1, idx + horizon)
    highs = [_high(row) for row in rows[idx : end_idx + 1]]
    lows = [_low(row) for row in rows[idx : end_idx + 1]]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    if not highs or not lows:
        return {
            "mfe_pct": None,
            "mae_pct": None,
            "entry_over_future_low_pct": None,
        }
    max_high = max(highs)
    min_low = min(lows)
    return {
        "mfe_pct": _round(max_high / reference_price - 1.0, 6),
        "mae_pct": _round(min_low / reference_price - 1.0, 6),
        "entry_over_future_low_pct": _round(reference_price / min_low - 1.0, 6)
        if min_low > 0
        else None,
    }


def _simulate_trade(
    rows: list[dict[str, Any]],
    *,
    ticker: str,
    strategy: str,
    signal_date: str,
    raw_entry_price: float,
    fill_date: str,
    shares: int,
    stop_price: float,
    target_price: float,
    window_end: str,
    source: str,
) -> dict[str, Any]:
    entry_fill = apply_entry_fill(raw_entry_price)
    fill_idx = _idx_for_date(rows, fill_date)
    end_idx = _last_idx_on_or_before_end(rows, window_end)
    if fill_idx is None or fill_idx > end_idx:
        return {
            "ticker": ticker,
            "strategy": strategy,
            "signal_date": signal_date,
            "status": "no_fill_row",
            "source": source,
            "pnl": 0.0,
            "shares": shares,
        }

    exit_price = None
    exit_raw_price = None
    exit_reason = None
    exit_date = None
    exit_idx = None
    for idx in range(fill_idx, end_idx + 1):
        row = rows[idx]
        opn = _open(row)
        high = _high(row)
        low = _low(row)
        if opn is None or high is None or low is None:
            continue
        if low <= stop_price:
            exit_raw_price = opn if opn < stop_price else stop_price
            exit_price = apply_stop_fill(opn, stop_price)
            exit_reason = "stop"
            exit_date = str(row["Date"])[:10]
            exit_idx = idx
            break
        if high >= target_price:
            exit_raw_price = opn if opn >= target_price else target_price
            exit_price = apply_target_fill(opn, target_price)
            exit_reason = "target"
            exit_date = str(row["Date"])[:10]
            exit_idx = idx
            break

    if exit_price is None:
        exit_idx = end_idx
        exit_row = rows[end_idx]
        raw_close = _close(exit_row)
        if raw_close is None:
            return {
                "ticker": ticker,
                "strategy": strategy,
                "signal_date": signal_date,
                "status": "missing_end_close",
                "source": source,
                "pnl": 0.0,
                "shares": shares,
            }
        exit_raw_price = raw_close
        exit_price = apply_slippage(raw_close, SLIPPAGE_BPS_TARGET, "sell")
        exit_reason = "end_of_window"
        exit_date = str(exit_row["Date"])[:10]

    cost = exit_price * ROUND_TRIP_COST_PCT * shares
    pnl = (exit_price - entry_fill) * shares - cost
    mfe_mae = _future_extrema(rows, fill_date, MFE_MAE_HORIZON, entry_fill)
    return {
        "ticker": ticker,
        "strategy": strategy,
        "signal_date": signal_date,
        "entry_date": fill_date,
        "exit_date": exit_date,
        "entry_idx": fill_idx,
        "exit_idx": exit_idx,
        "entry_price": _round(entry_fill, 4),
        "entry_raw_price": _round(raw_entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "exit_raw_price": _round(exit_raw_price, 4),
        "exit_reason": exit_reason,
        "shares": int(shares),
        "pnl": _round(pnl, 2),
        "pnl_pct_net": _round((exit_price - entry_fill) / entry_fill - ROUND_TRIP_COST_PCT, 6)
        if entry_fill
        else None,
        "status": "closed",
        "source": source,
        **mfe_mae,
    }


def _baseline_trade_from_event(
    event: dict[str, Any],
    rows: list[dict[str, Any]],
    window_end: str,
) -> dict[str, Any] | None:
    details = event.get("details") or {}
    snap = event.get("signal_snapshot") or {}
    ticker = str(event.get("ticker") or "").upper()
    shares = details.get("shares")
    fill_price = _float(details.get("fill_price"))
    fill_date = details.get("fill_date")
    stop = _float(snap.get("stop_price"))
    target = _float(snap.get("target_price"))
    if not ticker or not shares or fill_price is None or not fill_date or stop is None or target is None:
        return None
    return _simulate_trade(
        rows,
        ticker=ticker,
        strategy=str(event.get("strategy") or "unknown"),
        signal_date=str(event.get("date")),
        raw_entry_price=fill_price,
        fill_date=str(fill_date)[:10],
        shares=int(shares),
        stop_price=stop,
        target_price=target,
        window_end=window_end,
        source="baseline_next_open_proxy",
    )


def _variant_trade_from_event(
    event: dict[str, Any],
    rows: list[dict[str, Any]],
    window_end: str,
    *,
    wait_days: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    ticker = str(event.get("ticker") or "").upper()
    signal_date = str(event.get("date") or "")[:10]
    snap = event.get("signal_snapshot") or {}
    details = event.get("details") or {}
    signal_entry = _float(snap.get("entry_price"))
    stop = _float(snap.get("stop_price"))
    target = _float(snap.get("target_price"))
    shares = details.get("shares")
    signal_idx = _idx_for_date(rows, signal_date)

    meta = {
        "ticker": ticker,
        "signal_date": signal_date,
        "strategy": event.get("strategy"),
        "wait_days": wait_days,
        "status": None,
    }
    if (
        signal_idx is None
        or signal_entry is None
        or stop is None
        or target is None
        or not shares
    ):
        meta["status"] = "missing_inputs"
        return None, meta

    atr = _atr_at_idx(rows, signal_idx)
    if atr is None or atr <= 0:
        meta["status"] = "missing_atr"
        return None, meta

    limit_price = signal_entry - PULLBACK_ATR_FRACTION * atr
    pullback_pct = (signal_entry - limit_price) / signal_entry if signal_entry else None
    meta.update(
        {
            "atr14": _round(atr, 4),
            "limit_price": _round(limit_price, 4),
            "pullback_pct": _round(pullback_pct, 6),
        }
    )
    if pullback_pct is None or pullback_pct < MIN_PULLBACK_PCT or pullback_pct > MAX_PULLBACK_PCT:
        meta["status"] = "pullback_out_of_range"
        return None, meta

    last_idx = min(signal_idx + wait_days, _last_idx_on_or_before_end(rows, window_end))
    touched_sma_fail = 0
    for idx in range(signal_idx + 1, last_idx + 1):
        row = rows[idx]
        low = _low(row)
        opn = _open(row)
        close = _close(row)
        sma50 = _sma_at_idx(rows, idx, SMA_LOOKBACK)
        if low is None or opn is None or close is None:
            continue
        if low > limit_price:
            continue
        if sma50 is None or close <= sma50:
            touched_sma_fail += 1
            continue
        raw_fill = opn if opn <= limit_price else limit_price
        if raw_fill <= stop:
            meta["status"] = "stop_breach_entry"
            meta["fill_date"] = str(row["Date"])[:10]
            meta["raw_fill_price"] = _round(raw_fill, 4)
            return None, meta
        trade = _simulate_trade(
            rows,
            ticker=ticker,
            strategy=str(event.get("strategy") or "unknown"),
            signal_date=signal_date,
            raw_entry_price=raw_fill,
            fill_date=str(row["Date"])[:10],
            shares=int(shares),
            stop_price=stop,
            target_price=target,
            window_end=window_end,
            source=f"pullback_limit_{wait_days}d_0_5atr_proxy",
        )
        meta.update(
            {
                "status": "filled",
                "fill_date": trade.get("entry_date"),
                "raw_fill_price": _round(raw_fill, 4),
                "close_above_sma50": True,
                "sma50": _round(sma50, 4),
            }
        )
        return trade, meta

    meta["status"] = "sma50_fail_after_touch" if touched_sma_fail else "no_pullback_fill"
    meta["sma50_fail_touches"] = touched_sma_fail
    return None, meta


def _daily_equity_metrics(
    trades: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    start: str,
    end: str,
) -> dict[str, Any]:
    dates = [
        str(row["Date"])[:10]
        for row in spy_rows
        if str(row.get("Date"))[:10] >= start and str(row.get("Date"))[:10] <= end
    ]
    if not dates:
        return {
            "expected_value_score": None,
            "total_pnl": None,
            "total_return_pct": None,
            "sharpe_daily": None,
            "max_drawdown_pct": None,
            "win_rate": None,
            "trade_count": 0,
        }

    closed = [trade for trade in trades if trade.get("status") == "closed"]
    trade_count = len(closed)
    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in closed)
    wins = sum(1 for trade in closed if float(trade.get("pnl") or 0.0) > 0)

    equity_curve: list[float] = []
    realized_by_date: defaultdict[str, float] = defaultdict(float)
    for trade in closed:
        exit_date = str(trade.get("exit_date") or "")
        realized_by_date[exit_date] += float(trade.get("pnl") or 0.0)

    realized = 0.0
    peak = INITIAL_CAPITAL
    max_dd = 0.0
    for date_str in dates:
        realized += realized_by_date.get(date_str, 0.0)
        unrealized = 0.0
        for trade in closed:
            entry_date = str(trade.get("entry_date") or "")
            exit_date = str(trade.get("exit_date") or "")
            if not (entry_date <= date_str < exit_date):
                continue
            ticker = str(trade.get("ticker") or "").upper()
            rows = rows_by_ticker.get(ticker)
            if not rows:
                continue
            idx = _idx_for_date(rows, date_str)
            if idx is None:
                continue
            close = _close(rows[idx])
            entry_price = _float(trade.get("entry_price"))
            shares = int(trade.get("shares") or 0)
            if close is not None and entry_price is not None:
                unrealized += (close - entry_price) * shares
        equity = INITIAL_CAPITAL + realized + unrealized
        equity_curve.append(equity)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

    returns = []
    for prev, cur in zip(equity_curve, equity_curve[1:]):
        if prev:
            returns.append(cur / prev - 1.0)
    if len(returns) > 1:
        avg = sum(returns) / len(returns)
        stdev = statistics.pstdev(returns)
        sharpe = (avg / stdev) * math.sqrt(252) if stdev > 0 else None
    else:
        sharpe = None

    total_return = total_pnl / INITIAL_CAPITAL
    ev = total_return * sharpe if sharpe is not None else None
    return {
        "expected_value_score": _round(ev, 4),
        "total_pnl": _round(total_pnl, 2),
        "total_return_pct": _round(total_return, 4),
        "sharpe_daily": _round(sharpe, 2),
        "max_drawdown_pct": _round(max_dd, 4),
        "win_rate": _round(wins / trade_count, 4) if trade_count else None,
        "trade_count": trade_count,
    }


def _event_forward_packet(event: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    signal_date = str(event.get("date") or "")[:10]
    snap = event.get("signal_snapshot") or {}
    signal_entry = _float(snap.get("entry_price"))
    out: dict[str, Any] = {}
    for horizon in FORWARD_HORIZONS:
        out[f"forward_{horizon}d_return"] = _round(
            _forward_return(rows, signal_date, horizon),
            6,
        )
    if signal_entry is not None:
        out.update(_future_extrema(rows, signal_date, MFE_MAE_HORIZON, signal_entry))
    else:
        out.update(
            {
                "mfe_pct": None,
                "mae_pct": None,
                "entry_over_future_low_pct": None,
            }
        )
    return out


def _summarize_candidates(
    events: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    baseline_trades_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    pool_by_ticker = {ticker: "treatment" for ticker in TREATMENT_POOL}
    pool_by_ticker.update({ticker: "control" for ticker in CONTROL_POOL})

    def bucket(name: str) -> dict[str, Any]:
        if name not in buckets:
            buckets[name] = {
                "candidate_count": 0,
                "entered_count": 0,
                "decision_counts": Counter(),
                "strategy_counts": Counter(),
                "baseline_proxy_pnl": 0.0,
                "forward_returns": {h: [] for h in FORWARD_HORIZONS},
                "mfe_20d_pct": [],
                "mae_20d_pct": [],
                "entry_over_future_low_20d_pct": [],
            }
        return buckets[name]

    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        cohort = pool_by_ticker.get(ticker)
        if cohort is None:
            continue
        key = f"{event.get('date')}|{ticker}|{event.get('strategy')}"
        for name in (cohort, f"ticker:{ticker}"):
            item = bucket(name)
            item["candidate_count"] += 1
            decision = str(event.get("decision") or "unknown")
            item["decision_counts"][decision] += 1
            item["strategy_counts"][str(event.get("strategy") or "unknown")] += 1
            if decision == "entered":
                item["entered_count"] += 1
                item["baseline_proxy_pnl"] += float(
                    (baseline_trades_by_key.get(key) or {}).get("pnl") or 0.0
                )

        rows = rows_by_ticker.get(ticker)
        if not rows:
            continue
        packet = _event_forward_packet(event, rows)
        for name in (cohort, f"ticker:{ticker}"):
            item = bucket(name)
            for horizon in FORWARD_HORIZONS:
                value = packet.get(f"forward_{horizon}d_return")
                if value is not None:
                    item["forward_returns"][horizon].append(float(value))
            for field, target in (
                ("mfe_pct", "mfe_20d_pct"),
                ("mae_pct", "mae_20d_pct"),
                ("entry_over_future_low_pct", "entry_over_future_low_20d_pct"),
            ):
                value = packet.get(field)
                if value is not None:
                    item[target].append(float(value))

    result = {}
    for name, item in buckets.items():
        result[name] = {
            "candidate_count": item["candidate_count"],
            "entered_count": item["entered_count"],
            "decision_counts": dict(sorted(item["decision_counts"].items())),
            "strategy_counts": dict(sorted(item["strategy_counts"].items())),
            "baseline_proxy_pnl": _round(item["baseline_proxy_pnl"], 2),
            "forward_returns": {
                f"{horizon}d": _dist(values)
                for horizon, values in item["forward_returns"].items()
            },
            "mfe_20d_pct": _dist(item["mfe_20d_pct"]),
            "mae_20d_pct": _dist(item["mae_20d_pct"]),
            "entry_over_future_low_20d_pct": _dist(
                item["entry_over_future_low_20d_pct"]
            ),
        }
    return dict(sorted(result.items()))


def _candidate_artifact_validation(payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("candidate_events") or []
    attribution = payload.get("entry_execution_attribution") or {}
    reason_counts = Counter(str(event.get("decision") or "unknown") for event in events)
    attribution_counts = attribution.get("reason_counts") or {}
    return {
        "candidate_events_match": len(events) == attribution.get("candidate_events"),
        "reason_counts_match": dict(sorted(reason_counts.items()))
        == dict(sorted(attribution_counts.items())),
        "persisted_candidate_events": len(events),
        "attribution_candidate_events": attribution.get("candidate_events"),
        "persisted_reason_counts": dict(sorted(reason_counts.items())),
        "attribution_reason_counts": dict(sorted(attribution_counts.items())),
    }


def _window_replay(window_name: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot_path = REPO_ROOT / spec["snapshot"]
    candidate_path = REPO_ROOT / spec["candidate_events"]
    ohlcv = _load_ohlcv(snapshot_path)
    payload = _load_candidate_payload(candidate_path)
    events = payload["candidate_events"]

    baseline_trades: list[dict[str, Any]] = []
    baseline_by_key: dict[str, dict[str, Any]] = {}
    treatment_entered_events: list[dict[str, Any]] = []

    for event in events:
        if event.get("decision") != "entered":
            continue
        ticker = str(event.get("ticker") or "").upper()
        rows = ohlcv.get(ticker)
        if not rows:
            continue
        trade = _baseline_trade_from_event(event, rows, spec["end"])
        if not trade:
            continue
        baseline_trades.append(trade)
        key = f"{event.get('date')}|{ticker}|{event.get('strategy')}"
        baseline_by_key[key] = trade
        if ticker in TREATMENT_POOL:
            treatment_entered_events.append(event)

    spy_rows = ohlcv.get("SPY") or []
    proxy_before = _daily_equity_metrics(
        baseline_trades,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )

    variant_results = {}
    for variant_name, variant in VARIANTS.items():
        variant_trades = list(baseline_trades)
        details = []
        pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
        filled = 0
        removed = 0

        for event in treatment_entered_events:
            ticker = str(event.get("ticker") or "").upper()
            key = f"{event.get('date')}|{ticker}|{event.get('strategy')}"
            baseline_trade = baseline_by_key.get(key)
            if not baseline_trade:
                continue
            variant_trades = [trade for trade in variant_trades if trade is not baseline_trade]
            rows = ohlcv.get(ticker)
            if not rows:
                continue
            replacement, meta = _variant_trade_from_event(
                event,
                rows,
                spec["end"],
                wait_days=int(variant["wait_days"]),
            )
            baseline_pnl = float(baseline_trade.get("pnl") or 0.0)
            replacement_pnl = 0.0
            if replacement is not None and replacement.get("status") == "closed":
                variant_trades.append(replacement)
                replacement_pnl = float(replacement.get("pnl") or 0.0)
                filled += 1
            else:
                removed += 1
            pnl_delta = replacement_pnl - baseline_pnl
            pnl_delta_by_ticker[ticker] += pnl_delta
            details.append(
                {
                    "ticker": ticker,
                    "strategy": event.get("strategy"),
                    "signal_date": event.get("date"),
                    "baseline": {
                        "entry_date": baseline_trade.get("entry_date"),
                        "exit_date": baseline_trade.get("exit_date"),
                        "entry_price": baseline_trade.get("entry_price"),
                        "exit_price": baseline_trade.get("exit_price"),
                        "exit_reason": baseline_trade.get("exit_reason"),
                        "pnl": baseline_trade.get("pnl"),
                    },
                    "variant": replacement,
                    "meta": meta,
                    "pnl_delta": _round(pnl_delta, 2),
                }
            )

        proxy_after = _daily_equity_metrics(
            variant_trades,
            ohlcv,
            spy_rows,
            spec["start"],
            spec["end"],
        )
        ev_delta = None
        if (
            proxy_after.get("expected_value_score") is not None
            and proxy_before.get("expected_value_score") is not None
        ):
            ev_delta = proxy_after["expected_value_score"] - proxy_before["expected_value_score"]
        variant_results[variant_name] = {
            "metrics": proxy_after,
            "delta_vs_proxy_before": {
                "expected_value_score": _round(ev_delta, 4),
                "total_pnl": _round(proxy_after["total_pnl"] - proxy_before["total_pnl"], 2)
                if proxy_after.get("total_pnl") is not None
                and proxy_before.get("total_pnl") is not None
                else None,
                "sharpe_daily": _round(proxy_after["sharpe_daily"] - proxy_before["sharpe_daily"], 2)
                if proxy_after.get("sharpe_daily") is not None
                and proxy_before.get("sharpe_daily") is not None
                else None,
                "max_drawdown_pct": _round(
                    proxy_after["max_drawdown_pct"] - proxy_before["max_drawdown_pct"],
                    4,
                )
                if proxy_after.get("max_drawdown_pct") is not None
                and proxy_before.get("max_drawdown_pct") is not None
                else None,
                "trade_count": proxy_after["trade_count"] - proxy_before["trade_count"],
            },
            "touched_entered_events": len(treatment_entered_events),
            "filled_count": filled,
            "skipped_count": removed,
            "status_counts": dict(Counter(item["meta"].get("status") for item in details)),
            "pnl_delta_by_ticker": {
                ticker: _round(value, 2)
                for ticker, value in sorted(pnl_delta_by_ticker.items())
            },
            "details": details,
        }

    return {
        "window": spec,
        "candidate_artifact_validation": _candidate_artifact_validation(payload),
        "candidate_attribution": _summarize_candidates(events, ohlcv, baseline_by_key),
        "proxy_before_metrics": proxy_before,
        "baseline_proxy_trade_count": len(baseline_trades),
        "treatment_entered_events": len(treatment_entered_events),
        "variant_results": variant_results,
    }


def _aggregate_variant_results(by_window: dict[str, Any]) -> dict[str, Any]:
    out = {}
    baseline_ev_sum = sum(
        (window_data.get("proxy_before_metrics") or {}).get("expected_value_score") or 0.0
        for window_data in by_window.values()
    )
    baseline_pnl_sum = sum(
        (window_data.get("proxy_before_metrics") or {}).get("total_pnl") or 0.0
        for window_data in by_window.values()
    )

    for variant_name in VARIANTS:
        after_ev_sum = 0.0
        after_pnl_sum = 0.0
        touched_sum = 0
        filled_sum = 0
        by_window_delta = {}
        ticker_delta: defaultdict[str, float] = defaultdict(float)
        windows_ev_improved = 0
        windows_ev_regressed = 0
        max_dd_worsening = 0.0

        for window_name, window_data in by_window.items():
            variant = window_data["variant_results"][variant_name]
            metrics = variant["metrics"]
            delta = variant["delta_vs_proxy_before"]
            after_ev_sum += metrics.get("expected_value_score") or 0.0
            after_pnl_sum += metrics.get("total_pnl") or 0.0
            touched_sum += variant.get("touched_entered_events") or 0
            filled_sum += variant.get("filled_count") or 0
            ev_delta = delta.get("expected_value_score") or 0.0
            if ev_delta > 0:
                windows_ev_improved += 1
            elif ev_delta < 0:
                windows_ev_regressed += 1
            dd_delta = delta.get("max_drawdown_pct")
            if dd_delta is not None:
                max_dd_worsening = max(max_dd_worsening, dd_delta)
            by_window_delta[window_name] = delta
            for ticker, value in variant.get("pnl_delta_by_ticker", {}).items():
                ticker_delta[ticker] += float(value or 0.0)

        ev_delta_sum = after_ev_sum - baseline_ev_sum
        pnl_delta_sum = after_pnl_sum - baseline_pnl_sum
        positive_total = sum(value for value in ticker_delta.values() if value > 0)
        if positive_total > 0:
            max_single_ticker_positive_share = max(
                (value / positive_total for value in ticker_delta.values() if value > 0),
                default=0.0,
            )
        else:
            max_single_ticker_positive_share = None
        ev_delta_pct = ev_delta_sum / baseline_ev_sum if baseline_ev_sum else None
        gate4_passed = (
            ev_delta_pct is not None
            and ev_delta_pct > 0.10
            and windows_ev_improved >= 2
            and max_dd_worsening <= 0.01
            and touched_sum >= 8
            and (
                max_single_ticker_positive_share is None
                or max_single_ticker_positive_share <= 0.50
            )
        )
        out[variant_name] = {
            "baseline_proxy_expected_value_score_sum": _round(baseline_ev_sum, 4),
            "after_proxy_expected_value_score_sum": _round(after_ev_sum, 4),
            "expected_value_score_delta_sum": _round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": _round(ev_delta_pct, 6),
            "baseline_proxy_total_pnl_sum": _round(baseline_pnl_sum, 2),
            "after_proxy_total_pnl_sum": _round(after_pnl_sum, 2),
            "total_pnl_delta_sum": _round(pnl_delta_sum, 2),
            "windows_ev_improved": windows_ev_improved,
            "windows_ev_regressed": windows_ev_regressed,
            "max_drawdown_worsening_max": _round(max_dd_worsening, 4),
            "touched_entered_events": touched_sum,
            "filled_count": filled_sum,
            "max_single_ticker_positive_share": _round(
                max_single_ticker_positive_share,
                4,
            ),
            "pnl_delta_by_ticker": {
                ticker: _round(value, 2)
                for ticker, value in sorted(ticker_delta.items())
            },
            "by_window_delta": by_window_delta,
            "proxy_gate4_passed": gate4_passed,
        }
    return out


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _log_record(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
    best_variant: str,
    decision: str,
    rejection_reason: str | None,
) -> dict[str, Any]:
    baseline = _load_baseline_metrics()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["generated_at"],
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "entry_timing_replay",
        "alpha_hypothesis_category": "entry",
        "mechanism_family": "core_platform_entry_timing",
        "hypothesis": (
            "Core platform candidates seeded by NFLX/APP/META may be hurt by "
            "next-open chase entries; waiting for a small post-signal pullback "
            "could improve expectancy without changing ranking, sizing, exits, "
            "universe, LLM, or news."
        ),
        "single_causal_variable": "core_platform_entry_timing",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260426-051": (
                "Rejected broad multi-day pullback reclaim production replay; "
                "this run avoids broad source expansion and tests only already-entered "
                "core platform names."
            ),
            "exp-20260506-019": (
                "Rejected pullback/60d collision ranking; this run does not reorder "
                "candidates or change slots."
            ),
            "exp-20260505-011_and_020": (
                "Rejected consumer-platform universe promotion/gate; this run does "
                "not add any ticker or promote research names."
            ),
            "mechanism_insight_conflict": "none; entry timing is isolated from prior rejected ranking/universe variants",
        },
        "parameters": {
            "treatment_pool": list(TREATMENT_POOL),
            "control_pool": list(CONTROL_POOL),
            "excluded": {"TTD": "0 OHLCV rows in all three canonical snapshots"},
            "variants": {
                name: {
                    "wait_days": variant["wait_days"],
                    "limit": "signal_entry - 0.5 * ATR14",
                    "pullback_pct_range": [MIN_PULLBACK_PCT, MAX_PULLBACK_PCT],
                    "fill_condition": "low touches limit and close > SMA50",
                }
                for name, variant in VARIANTS.items()
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
            "best_variant": best_variant,
        },
        "before_metrics": baseline,
        "after_metrics": {
            variant: {
                name: payload["by_window"][name]["variant_results"][variant]["metrics"]
                for name in WINDOWS
            }
            for variant in VARIANTS
        },
        "proxy_before_metrics": {
            name: payload["by_window"][name]["proxy_before_metrics"] for name in WINDOWS
        },
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "gate4": {
            "passed": bool(aggregate[best_variant]["proxy_gate4_passed"]),
            "basis": (
                "Proxy replay from persisted candidate rows. Promotion still requires "
                "shared production/backtest entry policy if this ever passes."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news replay is deliberately locked out of this entry-timing experiment.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry nearby pullback wait/ATR values on the same core-platform cohort if this fails.",
            "A valid retry needs a materially different entry discriminator, such as event-quality context or forward paper evidence.",
            "If promoted later, implement the entry-timing rule as shared policy consumed by run.py and backtester.py with parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
    best_variant: str,
    decision: str,
    rejection_reason: str | None,
) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Core Platform Entry Timing",
        "",
        f"Decision: `{decision}`",
        f"Best variant: `{best_variant}`",
        "",
        "## Aggregate Proxy Gate",
        "",
        "| Variant | EV delta | PnL delta | Windows EV +/- | Touched | Filled | DD worsening | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in aggregate.items():
        lines.append(
            "| {name} | {ev} | {pnl} | {up}/{down} | {touched} | {filled} | {dd} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                pnl=metrics["total_pnl_delta_sum"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_entered_events"],
                filled=metrics["filled_count"],
                dd=metrics["max_drawdown_worsening_max"],
                gate=metrics["proxy_gate4_passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Cohort Read",
            "",
            "| Window | Treatment candidates | Treatment entered | Control candidates | Control entered |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for window_name, window_data in payload["by_window"].items():
        attribution = window_data["candidate_attribution"]
        treatment = attribution.get("treatment", {})
        control = attribution.get("control", {})
        lines.append(
            "| {window} | {tc} | {te} | {cc} | {ce} |".format(
                window=window_name,
                tc=treatment.get("candidate_count", 0),
                te=treatment.get("entered_count", 0),
                cc=control.get("candidate_count", 0),
                ce=control.get("entered_count", 0),
            )
        )
    if rejection_reason:
        lines.extend(["", "## Rejection Reason", "", rejection_reason])
    lines.extend(
        [
            "",
            "## Production Parity",
            "",
            "No production policy changed. This replay uses persisted candidate rows and is not a live order path.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    by_window = OrderedDict()
    for name, spec in WINDOWS.items():
        by_window[name] = _window_replay(name, spec)

    aggregate = _aggregate_variant_results(by_window)
    best_variant = _choose_best(aggregate)
    best_gate = bool(aggregate[best_variant]["proxy_gate4_passed"])
    decision = "accepted_for_shared_policy_followup" if best_gate else "rejected"
    rejection_reason = None
    if not best_gate:
        best = aggregate[best_variant]
        rejection_reason = (
            f"Best variant `{best_variant}` did not pass the pre-registered proxy gate: "
            f"EV delta {best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), "
            f"windows improved/regressed {best['windows_ev_improved']}/"
            f"{best['windows_ev_regressed']}, filled {best['filled_count']} of "
            f"{best['touched_entered_events']} touched entries."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "entry_timing_replay",
        "single_causal_variable": "core_platform_entry_timing",
        "treatment_pool": list(TREATMENT_POOL),
        "control_pool": list(CONTROL_POOL),
        "variants": VARIANTS,
        "windows": WINDOWS,
        "baseline_official_metrics": _load_baseline_metrics(),
        "by_window": by_window,
        "aggregate": aggregate,
        "best_variant": best_variant,
        "rejection_reason": rejection_reason,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "notes": [
            "Proxy replay only; not an executable production entry policy.",
            "Only baseline-entered treatment-pool candidates are altered.",
            "Skipped delayed fills do not backfill freed slots, preserving entry timing as the causal variable.",
        ],
    }

    log_record = _log_record(payload, aggregate, best_variant, decision, rejection_reason)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "hypothesis": log_record["hypothesis"],
        "single_causal_variable": "core_platform_entry_timing",
        "decision": decision,
        "best_variant": best_variant,
        "created_at": generated_at,
        "related_files": log_record["related_files"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(
        _artifact_markdown(payload, aggregate, best_variant, decision, rejection_reason),
        encoding="utf-8",
    )
    _append_jsonl(EXPERIMENT_LOG, log_record)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant,
        "best_delta": aggregate[best_variant],
        "out_json": str(OUT_JSON),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
