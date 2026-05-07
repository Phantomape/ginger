"""exp-20260507-014: core platform runner-exit replay.

Alpha search, replay-only. exp-20260507-008 showed that delayed pullback
entries did not fill the already-accepted core platform trades. exp-20260507-013
then found low upside capture in the same treatment cohort. This replay tests
one narrow exit lifecycle variable: after a treatment-pool trade hits the
baseline target, realize part of the position and let the rest run with a
simple SMA20 close exit, original hard stop, and 40-trading-day cap.

No production path, signal generation, ranking, sizing, universe membership,
add-ons, LLM/news behavior, or entry timing is changed by this script.
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
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage, apply_stop_fill  # noqa: E402


EXPERIMENT_ID = "exp-20260507-014"
SOURCE_EXPERIMENT_ID = "exp-20260507-013"
STEM = "core_platform_runner_exit_replay"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

INITIAL_CAPITAL = 100_000.0
SMA_LOOKBACK = 20
RUNNER_HOLD_DAYS = 40

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
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_late_strong.json"
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
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_mid_weak.json"
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
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        (
            "target_50_runner_sma20_40d",
            {
                "target_fraction": 0.50,
                "runner_fraction": 0.50,
            },
        ),
        (
            "target_67_runner_sma20_40d",
            {
                "target_fraction": 0.67,
                "runner_fraction": 0.33,
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


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
        clean_rows = [
            row for row in rows if isinstance(row, dict) and row.get("Date") is not None
        ]
        out[str(ticker).upper()] = sorted(clean_rows, key=lambda row: str(row["Date"]))
    return out


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


def _open(row: dict[str, Any]) -> float | None:
    return _float(row.get("Open"))


def _low(row: dict[str, Any]) -> float | None:
    return _float(row.get("Low"))


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date"))[:10]


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date_value(row): idx for idx, row in enumerate(rows)}


def _idx_for_date(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    return _date_index(rows).get(str(date_str)[:10])


def _last_idx_on_or_before(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    target = str(date_str)[:10]
    best = None
    for idx, row in enumerate(rows):
        if _date_value(row) <= target:
            best = idx
        else:
            break
    return best


def _sma_at_idx(rows: list[dict[str, Any]], idx: int, lookback: int = SMA_LOOKBACK) -> float | None:
    if idx + 1 < lookback:
        return None
    closes = [_close(row) for row in rows[idx - lookback + 1 : idx + 1]]
    clean = [value for value in closes if value is not None]
    if len(clean) != lookback:
        return None
    return sum(clean) / lookback


def _window_dates(spy_rows: list[dict[str, Any]], start: str, end: str) -> list[str]:
    return [
        _date_value(row)
        for row in spy_rows
        if start <= _date_value(row) <= end
    ]


def _parent_key(trade: dict[str, Any]) -> str:
    explicit = trade.get("parent_trade_key") or trade.get("trade_key")
    if explicit:
        return str(explicit)
    return "|".join(
        [
            str(trade.get("ticker") or ""),
            str(trade.get("strategy") or ""),
            str(trade.get("entry_date") or ""),
            str(trade.get("entry_price") or ""),
        ]
    )


def _as_closed_trade(trade: dict[str, Any]) -> dict[str, Any]:
    out = dict(trade)
    out["status"] = "closed"
    out["parent_trade_key"] = _parent_key(out)
    out.setdefault("synthetic_leg", "baseline_full")
    return out


def _leg_pnl(entry_price: float, exit_price: float, shares: int) -> tuple[float, float]:
    pnl = (exit_price - entry_price) * shares - exit_price * ROUND_TRIP_COST_PCT * shares
    pnl_pct = (exit_price - entry_price) / entry_price - ROUND_TRIP_COST_PCT
    return pnl, pnl_pct


def _synthetic_leg(
    trade: dict[str, Any],
    *,
    shares: int,
    exit_date: str,
    exit_price: float,
    exit_raw_price: float | None,
    exit_reason: str,
    leg_name: str,
) -> dict[str, Any]:
    entry_price = _float(trade.get("entry_price"))
    if entry_price is None:
        raise RuntimeError(f"Missing entry_price for {trade.get('trade_key')}")
    pnl, pnl_pct = _leg_pnl(entry_price, exit_price, shares)
    parent = _parent_key(trade)
    out = dict(trade)
    out.update(
        {
            "trade_key": f"{parent}:{leg_name}",
            "parent_trade_key": parent,
            "synthetic_leg": leg_name,
            "status": "closed",
            "shares": int(shares),
            "exit_date": exit_date,
            "exit_price": _round(exit_price, 4),
            "exit_raw_price": _round(exit_raw_price, 4),
            "exit_reason": exit_reason,
            "pnl": _round(pnl, 2),
            "pnl_pct_net": _round(pnl_pct, 6),
        }
    )
    return out


def _runner_exit(
    rows: list[dict[str, Any]],
    trade: dict[str, Any],
    window_end: str,
) -> dict[str, Any]:
    entry_idx = _idx_for_date(rows, trade.get("entry_date"))
    target_idx = _idx_for_date(rows, trade.get("exit_date"))
    end_idx = _last_idx_on_or_before(rows, window_end)
    stop_price = _float(trade.get("stop_price"))
    if entry_idx is None or target_idx is None or end_idx is None or stop_price is None:
        return {
            "status": "missing_runner_inputs",
            "exit_idx": target_idx,
            "exit_date": trade.get("exit_date"),
            "exit_price": _float(trade.get("exit_price")),
            "exit_raw_price": _float(trade.get("exit_raw_price")),
            "exit_reason": "baseline_target",
        }

    cap_idx = min(entry_idx + RUNNER_HOLD_DAYS, end_idx)
    start_idx = target_idx + 1
    if start_idx > cap_idx:
        return {
            "status": "no_runner_window",
            "exit_idx": target_idx,
            "exit_date": trade.get("exit_date"),
            "exit_price": _float(trade.get("exit_price")),
            "exit_raw_price": _float(trade.get("exit_raw_price")),
            "exit_reason": "baseline_target",
        }

    for idx in range(start_idx, cap_idx + 1):
        row = rows[idx]
        opn = _open(row)
        low = _low(row)
        close = _close(row)
        if opn is not None and low is not None and low <= stop_price:
            exit_price = apply_stop_fill(opn, stop_price)
            exit_raw = opn if opn < stop_price else stop_price
            return {
                "status": "runner_closed",
                "exit_idx": idx,
                "exit_date": _date_value(row),
                "exit_price": exit_price,
                "exit_raw_price": exit_raw,
                "exit_reason": "runner_hard_stop",
            }
        sma20 = _sma_at_idx(rows, idx)
        if close is not None and sma20 is not None and close < sma20:
            return {
                "status": "runner_closed",
                "exit_idx": idx,
                "exit_date": _date_value(row),
                "exit_price": apply_slippage(close, SLIPPAGE_BPS_TARGET, "sell"),
                "exit_raw_price": close,
                "exit_reason": "runner_sma20_close",
            }

    row = rows[cap_idx]
    close = _close(row)
    if close is None:
        return {
            "status": "missing_cap_close",
            "exit_idx": target_idx,
            "exit_date": trade.get("exit_date"),
            "exit_price": _float(trade.get("exit_price")),
            "exit_raw_price": _float(trade.get("exit_raw_price")),
            "exit_reason": "baseline_target",
        }
    reason = "runner_time_cap_40d" if cap_idx == entry_idx + RUNNER_HOLD_DAYS else "runner_end_of_window"
    return {
        "status": "runner_closed",
        "exit_idx": cap_idx,
        "exit_date": _date_value(row),
        "exit_price": apply_slippage(close, SLIPPAGE_BPS_TARGET, "sell"),
        "exit_raw_price": close,
        "exit_reason": reason,
    }


def _variant_legs(
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
    window_end: str,
    *,
    target_fraction: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline = _as_closed_trade(trade)
    ticker = str(trade.get("ticker") or "").upper()
    meta = {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "baseline_exit_date": trade.get("exit_date"),
        "baseline_exit_reason": trade.get("exit_reason"),
        "baseline_pnl": _round(trade.get("pnl"), 2),
        "baseline_shares": int(trade.get("shares") or 0),
        "status": "unchanged",
    }
    if ticker not in TREATMENT_POOL:
        meta["status"] = "not_treatment"
        return [baseline], meta
    if trade.get("exit_reason") != "target":
        meta["status"] = "not_target_exit"
        return [baseline], meta

    shares = int(trade.get("shares") or 0)
    entry_price = _float(trade.get("entry_price"))
    target_exit = _float(trade.get("exit_price"))
    if shares < 2 or entry_price is None or target_exit is None:
        meta["status"] = "insufficient_split_inputs"
        return [baseline], meta

    target_shares = max(1, min(shares - 1, int(round(shares * target_fraction))))
    runner_shares = shares - target_shares
    runner = _runner_exit(rows, trade, window_end)
    runner_exit_price = _float(runner.get("exit_price"))
    if runner_exit_price is None:
        meta["status"] = "missing_runner_exit"
        return [baseline], meta

    target_leg = _synthetic_leg(
        trade,
        shares=target_shares,
        exit_date=str(trade.get("exit_date"))[:10],
        exit_price=target_exit,
        exit_raw_price=_float(trade.get("exit_raw_price")),
        exit_reason="target_partial",
        leg_name="target_leg",
    )
    runner_leg = _synthetic_leg(
        trade,
        shares=runner_shares,
        exit_date=str(runner.get("exit_date"))[:10],
        exit_price=runner_exit_price,
        exit_raw_price=_float(runner.get("exit_raw_price")),
        exit_reason=str(runner.get("exit_reason") or "runner_exit"),
        leg_name="runner_leg",
    )
    variant_pnl = float(target_leg.get("pnl") or 0.0) + float(runner_leg.get("pnl") or 0.0)
    baseline_pnl = _float(trade.get("pnl")) or 0.0
    meta.update(
        {
            "status": "modified",
            "target_shares": target_shares,
            "runner_shares": runner_shares,
            "target_fraction_actual": _round(target_shares / shares, 6),
            "runner_fraction_actual": _round(runner_shares / shares, 6),
            "runner_status": runner.get("status"),
            "runner_exit_date": runner.get("exit_date"),
            "runner_exit_reason": runner.get("exit_reason"),
            "runner_exit_price": _round(runner_exit_price, 4),
            "variant_pnl": _round(variant_pnl, 2),
            "pnl_delta": _round(variant_pnl - baseline_pnl, 2),
        }
    )
    return [target_leg, runner_leg], meta


def _daily_equity_metrics(
    trades: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    start: str,
    end: str,
) -> dict[str, Any]:
    dates = _window_dates(spy_rows, start, end)
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

    closed = [trade for trade in trades if trade.get("exit_date") and trade.get("entry_date")]
    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in closed)
    parent_pnl: defaultdict[str, float] = defaultdict(float)
    for trade in closed:
        parent_pnl[_parent_key(trade)] += float(trade.get("pnl") or 0.0)
    trade_count = len(parent_pnl)
    wins = sum(1 for pnl in parent_pnl.values() if pnl > 0)

    realized_by_date: defaultdict[str, float] = defaultdict(float)
    for trade in closed:
        realized_by_date[str(trade.get("exit_date") or "")[:10]] += float(
            trade.get("pnl") or 0.0
        )

    equity_curve: list[float] = []
    realized = 0.0
    peak = INITIAL_CAPITAL
    max_dd = 0.0
    for date_str in dates:
        realized += realized_by_date.get(date_str, 0.0)
        unrealized = 0.0
        for trade in closed:
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if not (entry_date <= date_str < exit_date):
                continue
            ticker = str(trade.get("ticker") or "").upper()
            rows = rows_by_ticker.get(ticker)
            if not rows:
                continue
            idx = _idx_for_date(rows, date_str)
            close = _close(rows[idx]) if idx is not None else None
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


def _window_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") if isinstance(result.get("benchmarks"), dict) else {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = _load_ohlcv(REPO_ROOT / spec["snapshot"])
    result = _load_json(REPO_ROOT / spec["backtest_results"])
    trades = [_as_closed_trade(trade) for trade in result.get("trades") or []]
    spy_rows = ohlcv.get("SPY") or []
    proxy_before = _daily_equity_metrics(trades, ohlcv, spy_rows, spec["start"], spec["end"])

    variant_results = {}
    treatment_trades = [
        trade for trade in trades if str(trade.get("ticker") or "").upper() in TREATMENT_POOL
    ]
    eligible_targets = [trade for trade in treatment_trades if trade.get("exit_reason") == "target"]

    for variant_name, variant in VARIANTS.items():
        variant_trades: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        runner_reason_counts: Counter[str] = Counter()
        pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
        changed_count = 0

        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            rows = ohlcv.get(ticker)
            if ticker in TREATMENT_POOL and rows:
                replacement_legs, meta = _variant_legs(
                    trade,
                    rows,
                    spec["end"],
                    target_fraction=float(variant["target_fraction"]),
                )
                status_counts[str(meta.get("status"))] += 1
                if meta.get("status") == "modified":
                    changed_count += 1
                    runner_reason_counts[str(meta.get("runner_exit_reason"))] += 1
                    pnl_delta_by_ticker[ticker] += float(meta.get("pnl_delta") or 0.0)
                    details.append(meta)
                variant_trades.extend(replacement_legs)
            else:
                variant_trades.append(trade)

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
            "touched_treatment_trades": len(treatment_trades),
            "eligible_target_trades": len(eligible_targets),
            "changed_target_trades": changed_count,
            "status_counts": dict(sorted(status_counts.items())),
            "runner_exit_reason_counts": dict(sorted(runner_reason_counts.items())),
            "pnl_delta_by_ticker": {
                ticker: _round(value, 2)
                for ticker, value in sorted(pnl_delta_by_ticker.items())
            },
            "details": details,
        }

    return {
        "window": name,
        "window_spec": spec,
        "official_baseline_metrics": _window_metrics(result),
        "proxy_before_metrics": proxy_before,
        "baseline_trade_count": len(trades),
        "treatment_trade_count": len(treatment_trades),
        "eligible_target_trade_count": len(eligible_targets),
        "variant_results": variant_results,
    }


def _max_single_ticker_positive_share(pnl_delta_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    baseline_ev_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("expected_value_score") or 0.0
        for window in by_window.values()
    )
    baseline_pnl_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("total_pnl") or 0.0
        for window in by_window.values()
    )
    out: dict[str, Any] = {}
    for variant_name in VARIANTS:
        after_ev_sum = 0.0
        after_pnl_sum = 0.0
        touched_sum = 0
        eligible_sum = 0
        changed_sum = 0
        improved = 0
        regressed = 0
        max_dd_worsening = 0.0
        by_window_delta = {}
        pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
        status_counts: Counter[str] = Counter()
        runner_exit_reason_counts: Counter[str] = Counter()

        for window_name, window in by_window.items():
            variant = window["variant_results"][variant_name]
            metrics = variant["metrics"]
            delta = variant["delta_vs_proxy_before"]
            after_ev_sum += metrics.get("expected_value_score") or 0.0
            after_pnl_sum += metrics.get("total_pnl") or 0.0
            touched_sum += variant.get("touched_treatment_trades") or 0
            eligible_sum += variant.get("eligible_target_trades") or 0
            changed_sum += variant.get("changed_target_trades") or 0
            ev_delta = delta.get("expected_value_score") or 0.0
            if ev_delta > 0:
                improved += 1
            elif ev_delta < 0:
                regressed += 1
            dd_delta = delta.get("max_drawdown_pct")
            if dd_delta is not None:
                max_dd_worsening = max(max_dd_worsening, dd_delta)
            by_window_delta[window_name] = delta
            for ticker, value in variant.get("pnl_delta_by_ticker", {}).items():
                pnl_delta_by_ticker[ticker] += float(value or 0.0)
            status_counts.update(variant.get("status_counts") or {})
            runner_exit_reason_counts.update(variant.get("runner_exit_reason_counts") or {})

        ev_delta_sum = after_ev_sum - baseline_ev_sum
        pnl_delta_sum = after_pnl_sum - baseline_pnl_sum
        ev_delta_pct = ev_delta_sum / abs(baseline_ev_sum) if baseline_ev_sum else None
        ticker_deltas = {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())
        }
        max_single_share = _max_single_ticker_positive_share(dict(pnl_delta_by_ticker))
        gate_passed = (
            ev_delta_pct is not None
            and ev_delta_pct > 0.10
            and improved >= 2
            and max_dd_worsening <= 0.01
            and touched_sum >= 8
            and changed_sum >= 3
            and (max_single_share is None or max_single_share <= 0.50)
        )
        out[variant_name] = {
            "baseline_proxy_expected_value_score_sum": _round(baseline_ev_sum, 4),
            "after_proxy_expected_value_score_sum": _round(after_ev_sum, 4),
            "expected_value_score_delta_sum": _round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": _round(ev_delta_pct, 6),
            "baseline_proxy_total_pnl_sum": _round(baseline_pnl_sum, 2),
            "after_proxy_total_pnl_sum": _round(after_pnl_sum, 2),
            "total_pnl_delta_sum": _round(pnl_delta_sum, 2),
            "windows_ev_improved": improved,
            "windows_ev_regressed": regressed,
            "max_drawdown_worsening_max": _round(max_dd_worsening, 4),
            "touched_treatment_trades": touched_sum,
            "eligible_target_trades": eligible_sum,
            "changed_target_trades": changed_sum,
            "status_counts": dict(sorted(status_counts.items())),
            "runner_exit_reason_counts": dict(sorted(runner_exit_reason_counts.items())),
            "max_single_ticker_positive_share": _round(max_single_share, 4),
            "pnl_delta_by_ticker": ticker_deltas,
            "by_window_delta": by_window_delta,
            "proxy_gate4_passed": gate_passed,
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


def _official_baseline_sum(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("expected_value_score")
                or 0.0
                for window in by_window.values()
            ),
            4,
        ),
        "total_pnl_sum": _round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("total_pnl") or 0.0
                for window in by_window.values()
            ),
            2,
        ),
        "trade_count_sum": sum(
            int((window.get("official_baseline_metrics") or {}).get("trade_count") or 0)
            for window in by_window.values()
        ),
    }


def _log_record(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
    best_variant: str,
    decision: str,
    rejection_reason: str | None,
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "exit",
        "change_type": "runner_exit_replay",
        "mechanism_family": "core_platform_exit_capture",
        "single_causal_variable": "core_platform_runner_exit_policy",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "before_metrics": {
            name: window["official_baseline_metrics"]
            for name, window in payload["by_window"].items()
        },
        "proxy_before_metrics": {
            name: window["proxy_before_metrics"] for name, window in payload["by_window"].items()
        },
        "after_metrics": {
            variant: {
                name: payload["by_window"][name]["variant_results"][variant]["metrics"]
                for name in payload["by_window"]
            }
            for variant in VARIANTS
        },
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": aggregate[best_variant][
            "expected_value_score_delta_sum"
        ],
        "gate4": {
            "passed": bool(aggregate[best_variant]["proxy_gate4_passed"]),
            "basis": (
                "Replay-only proxy from official baseline trades. Promotion would "
                "require moving the runner policy into shared run.py/backtester.py code."
            ),
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM/news replay remains locked out; this only changes synthetic "
                "post-target exit timing for already-entered treatment trades."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }


def _ticket(best_variant: str, decision: str, aggregate: dict[str, Any]) -> dict[str, Any]:
    best = aggregate[best_variant]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Core platform runner-exit replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "next_action": (
            "Promote only after shared-policy implementation and parity tests."
            if best["proxy_gate4_passed"]
            else "Do not promote; avoid nearby core-platform target-half runner variants without new evidence."
        ),
    }


def _artifact_markdown(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
    best_variant: str,
    decision: str,
    rejection_reason: str | None,
) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Core Platform Runner Exit Replay",
        "",
        f"Decision: `{decision}`",
        f"Best variant: `{best_variant}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Baseline",
        "",
        "| EV sum | PnL sum | Trades |",
        "|---:|---:|---:|",
        "| {ev} | {pnl} | {trades} |".format(
            ev=payload["official_baseline_metrics"]["expected_value_score_sum"],
            pnl=payload["official_baseline_metrics"]["total_pnl_sum"],
            trades=payload["official_baseline_metrics"]["trade_count_sum"],
        ),
        "",
        "## Variants",
        "",
        "| Variant | Target fraction | Runner exit |",
        "|---|---:|---|",
    ]
    for name, variant in VARIANTS.items():
        lines.append(
            "| {name} | {target} | SMA20 close, original hard stop, 40d cap |".format(
                name=name,
                target=variant["target_fraction"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Replay",
            "",
            "| Variant | EV delta | PnL delta | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for name, metrics in aggregate.items():
        lines.append(
            "| {name} | {ev} | {pnl} | {up}/{down} | {touched} | {changed} | {dd} | {share} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                pnl=metrics["total_pnl_delta_sum"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_treatment_trades"],
                changed=metrics["changed_target_trades"],
                dd=metrics["max_drawdown_worsening_max"],
                share=metrics["max_single_ticker_positive_share"],
                gate="PASS" if metrics["proxy_gate4_passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Replay only; no production path changed.",
            "- Single causal variable: post-target runner exit policy for treatment-pool trades.",
            "- Entries, ranking, sizing, add-ons, universe, LLM/news, and earnings behavior are locked.",
            "- This is not a repeat of broad pullback, pullback-RS ranking, consumer-platform universe promotion, or full-position ATR trailing exits.",
        ]
    )
    if rejection_reason:
        lines.extend(["", "## Rejection Reason", "", rejection_reason])
    return "\n".join(lines) + "\n"


def main() -> None:
    by_window = OrderedDict((name, _replay_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    best_variant = _choose_best(aggregate)
    best = aggregate[best_variant]
    decision = "accepted_for_promotion_review" if best["proxy_gate4_passed"] else "rejected"
    rejection_reason = None
    if not best["proxy_gate4_passed"]:
        rejection_reason = (
            f"Best variant `{best_variant}` failed the pre-registered proxy gate: "
            f"EV delta {best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), windows improved/regressed "
            f"{best['windows_ev_improved']}/{best['windows_ev_regressed']}, "
            f"changed target trades {best['changed_target_trades']}, max DD worsening "
            f"{best['max_drawdown_worsening_max']}, single ticker positive share "
            f"{best['max_single_ticker_positive_share']}."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Core platform trades may be entering correctly but exiting target "
            "winners too early; a partial target plus simple SMA20 runner may "
            "improve upside capture without changing entries, ranking, sizing, "
            "or the production path."
        ),
        "source_experiment": SOURCE_EXPERIMENT_ID,
        "history_check": {
            "exp-20260507-008": (
                "Rejected core-platform pullback entry timing; this run changes "
                "only post-target exit lifecycle."
            ),
            "exp-20260507-013": (
                "Observed-only diagnostic found 11 treatment trades, 5 runner "
                "candidates, and median treatment 40d MFE capture of 0.410675."
            ),
            "exp-20260506-010": (
                "Rejected event-leader target-half-trail family. This retry is "
                "allowed only because exp-013 supplies a different cohort and "
                "fresh lifecycle capture evidence."
            ),
            "exp-20260503-009": (
                "Rejected full-position ATR trailing exit. This replay never "
                "trails the full position and touches only target winners."
            ),
            "exp-20260505-011_and_020": (
                "Rejected consumer-platform universe/gate; this run adds no "
                "ticker and changes no universe membership."
            ),
            "mechanism_insight_conflict": (
                "Near-repeat risk is controlled by using a new core-platform "
                "capture diagnostic, no ATR trail, no full-exit trail, and no "
                "entry/ranking/universe changes."
            ),
        },
        "parameters": {
            "treatment_pool": list(TREATMENT_POOL),
            "control_pool_diagnostic_only": list(CONTROL_POOL),
            "variants": VARIANTS,
            "runner_exit": {
                "activation": "treatment-pool trades with baseline exit_reason == target",
                "target_leg_fill": "baseline target fill price and date",
                "runner_exit_rule": "first close below SMA20 after target date",
                "hard_stop": "original stop_price with shared stop fill model",
                "time_cap_trading_days_from_entry": RUNNER_HOLD_DAYS,
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry timing",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "earnings strategy",
            ],
            "promotion_gate": {
                "expected_value_score_delta_pct": "> 10%",
                "windows_ev_improved": ">= 2 of 3",
                "max_drawdown_worsening": "<= 0.01",
                "touched_treatment_trades": ">= 8",
                "changed_target_trades": ">= 3",
                "single_ticker_positive_contribution": "<= 50%",
            },
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "best_variant": best_variant,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_exits": False,
            "alters_sizing": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
        },
        "next_retry_requires": [
            "Do not retry nearby target-half runner percentages on this same sample if rejected.",
            "A valid retry needs event/news semantics, forward paper evidence, or a broader lifecycle discriminator.",
            "If promoted later, implement as shared policy consumed by run.py and backtester.py with parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }

    log_record = _log_record(payload, aggregate, best_variant, decision, rejection_reason)
    ticket = _ticket(best_variant, decision, aggregate)

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(
        _artifact_markdown(payload, aggregate, best_variant, decision, rejection_reason),
        encoding="utf-8",
    )
    _append_jsonl(EXPERIMENT_LOG, log_record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "best_delta": aggregate[best_variant],
                "out_json": str(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
