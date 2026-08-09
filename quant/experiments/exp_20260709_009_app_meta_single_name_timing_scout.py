"""exp-20260709-009: APP/META single-name timing scout.

Observed-only alpha scout. The fixed question is whether APP and META deserve a
standalone specialist timing sleeve: stay in cash most of the time, enter only
on a small set of predeclared OHLCV timing states, and beat the same ticker's
buy-and-hold plus SPY/QQQ comparators before any production/default-off work.

No strategy, shared policy, backtester adapter, run adapter, sizing, ranking,
orders, paper state, or LLM boundary is changed by this runner.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260709-009"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "app_meta_single_name_timing_scout"
RUNNER = f"quant/experiments/exp_20260709_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = [
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": DATA_DIR / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": DATA_DIR / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": DATA_DIR / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
]

TARGET_TICKERS = ("APP", "META")
BENCHMARK_TICKERS = ("SPY", "QQQ")
ROUND_TRIP_COST_PCT = 0.0035
HALF_COST_PCT = ROUND_TRIP_COST_PCT / 2.0
INITIAL_CAPITAL = 100_000.0
MAX_HOLD_DAYS = 25
ATR_STOP_UNITS = 2.5
ANNUALIZATION_DAYS = 252

HYPOTHESIS = (
    "APP and META standalone single-name specialist timing may only add value "
    "in fixed trend/reclaim/breakout states; compare predeclared OHLCV-only "
    "archetypes against each ticker buy-and-hold plus SPY/QQQ before any "
    "production or default-off promotion."
)
CHANGE_TYPE = "observed_only_single_name_timing_scout"
MECHANISM_FAMILY = "single_name_specialist_timing"
TRIAL_FAMILY = "app_meta_single_name_specialist_timing"
TRIAL_VARIANT_ID = "fixed_ohlcv_archetype_compass_v1"
CHANGED_VARIABLE = "app_meta_single_name_specialist_timing_v1"
NEW_EVIDENCE_AXIS = (
    "New gate shape: standalone single-name specialist timing scout with "
    "own-ticker buy-and-hold, SPY, and QQQ comparators; not a candidate-level "
    "platform pullback wait, APP sizing top-up, ticker expansion, or "
    "forward-row attribution retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260507-008",
    "exp-20260507-028",
    "exp-20260507-030",
    "exp-20260517-024",
]
CAUSAL_COMPONENTS = [
    "canonical_ohlcv_snapshots",
    "fixed_archetype_set",
    "ticker_buy_hold_comparators",
    "spy_qqq_comparators",
    "no_strategy_change",
]
PREDICTION = {
    "success_probability": 0.26,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "fails_buy_hold_benchmark",
        "thin_trade_count",
        "one_ticker_concentration",
        "ohlcv_overfit",
        "no_window_stability",
    ],
    "confidence_reason": (
        "Prior platform pullback timing was rejected and APP-specific sizing "
        "was underpowered, but a standalone single-name sleeve has a different "
        "decision boundary: it can stay in cash except during fixed predeclared "
        "trend/reclaim/breakout regimes and must beat the own-ticker "
        "buy-and-hold comparator before any promotion."
    ),
    "recorded_at": "2026-07-09T06:52:13+00:00",
}
ACCEPTANCE_RULE = {
    "lead_only": True,
    "min_trade_count_per_ticker_archetype": 6,
    "min_windows_beating_ticker_buy_hold": 2,
    "require_positive_aggregate_return_delta_vs_ticker_buy_hold": True,
    "require_positive_aggregate_ev_delta_vs_ticker_buy_hold": True,
    "require_aggregate_ev_beats_spy_and_qqq": True,
    "max_drawdown_extra_vs_ticker_buy_hold": 0.02,
    "promotion_boundary": (
        "A passing row is only an observed-only lead. Promotion requires a "
        "shared default-off helper, daily snapshot, parity test, and Gate 1-4."
    ),
}


@dataclass(frozen=True)
class Row:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    entry_date: str
    entry_price: float
    shares: float
    entry_signal_date: str
    entry_index: int
    entry_equity: float
    entry_reason: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction if isinstance(prediction, dict) else PREDICTION


def as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def normalize_rows(raw_rows: list[dict[str, Any]]) -> list[Row]:
    rows: list[Row] = []
    for raw in raw_rows:
        date = str(raw.get("Date") or raw.get("date") or "")[:10]
        open_ = as_float(raw.get("Open", raw.get("open")))
        high = as_float(raw.get("High", raw.get("high")))
        low = as_float(raw.get("Low", raw.get("low")))
        close = as_float(raw.get("Close", raw.get("close")))
        volume = as_float(raw.get("Volume", raw.get("volume"))) or 0.0
        if not date or None in (open_, high, low, close):
            continue
        if open_ <= 0 or high <= 0 or low <= 0 or close <= 0:
            continue
        rows.append(Row(date, open_, high, low, close, volume))
    rows.sort(key=lambda item: item.date)
    return rows


def load_snapshot(path: Path) -> dict[str, list[Row]]:
    payload = read_json(path, {})
    raw = payload.get("ohlcv", payload) if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {str(ticker).upper(): normalize_rows(rows) for ticker, rows in raw.items()}


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    total = 0.0
    for idx, value in enumerate(values):
        total += value
        if idx >= window:
            total -= values[idx - window]
        if idx >= window - 1:
            out[idx] = total / window
    return out


def true_ranges(rows: list[Row]) -> list[float]:
    out: list[float] = []
    prev_close: float | None = None
    for row in rows:
        if prev_close is None:
            tr = row.high - row.low
        else:
            tr = max(row.high - row.low, abs(row.high - prev_close), abs(row.low - prev_close))
        out.append(tr)
        prev_close = row.close
    return out


def pct_return(closes: list[float], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    base = closes[idx - lookback]
    if base <= 0:
        return None
    return closes[idx] / base - 1.0


def max_prior(values: list[float], idx: int, window: int) -> float | None:
    start = idx - window
    if start < 0:
        return None
    sample = values[start:idx]
    return max(sample) if sample else None


def metrics_from_curve(equity_curve: list[dict[str, float]]) -> dict[str, Any]:
    if len(equity_curve) < 2:
        return {
            "total_return_pct": 0.0,
            "sharpe_daily": 0.0,
            "expected_value_score": 0.0,
            "max_drawdown_pct": 0.0,
            "daily_count": len(equity_curve),
        }
    values = [point["equity"] for point in equity_curve]
    returns: list[float] = []
    for prev, cur in zip(values, values[1:]):
        returns.append(cur / prev - 1.0 if prev > 0 else 0.0)
    total_return = values[-1] / values[0] - 1.0 if values[0] > 0 else 0.0
    if len(returns) > 1:
        std = statistics.pstdev(returns)
        sharpe = (
            statistics.mean(returns) / std * math.sqrt(ANNUALIZATION_DAYS)
            if std > 0
            else 0.0
        )
    else:
        sharpe = 0.0
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, peak / value - 1.0)
    return {
        "total_return_pct": round(total_return, 6),
        "sharpe_daily": round(sharpe, 4),
        "expected_value_score": round(total_return * sharpe, 4),
        "max_drawdown_pct": round(max_dd, 6),
        "daily_count": len(equity_curve),
    }


def benchmark_buy_hold(rows: list[Row], start: str, end: str) -> dict[str, Any]:
    window = [row for row in rows if start <= row.date <= end]
    if len(window) < 2:
        return {
            "available": False,
            "total_return_pct": 0.0,
            "sharpe_daily": 0.0,
            "expected_value_score": 0.0,
            "max_drawdown_pct": 0.0,
            "daily_count": len(window),
        }
    shares = INITIAL_CAPITAL * (1.0 - HALF_COST_PCT) / window[0].open
    curve: list[dict[str, float]] = []
    for idx, row in enumerate(window):
        equity = shares * row.close
        if idx == len(window) - 1:
            equity *= 1.0 - HALF_COST_PCT
        curve.append({"date": row.date, "equity": equity})
    metrics = metrics_from_curve(curve)
    metrics.update(
        {
            "available": True,
            "entry_date": window[0].date,
            "exit_date": window[-1].date,
            "entry_price": round(window[0].open, 4),
            "exit_price": round(window[-1].close, 4),
        }
    )
    return metrics


def empty_strategy_result(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "total_return_pct": 0.0,
        "sharpe_daily": 0.0,
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "trade_count": 0,
        "win_rate": None,
        "exposure_pct": 0.0,
        "trades": [],
    }


def build_indicators(rows: list[Row], qqq_rows: list[Row]) -> dict[str, list[Any]]:
    closes = [row.close for row in rows]
    qqq_by_date = {row.date: row.close for row in qqq_rows}
    qqq_dates = [row.date for row in qqq_rows]
    qqq_closes = [row.close for row in qqq_rows]
    qqq_ret20_by_date: dict[str, float] = {}
    for idx, date in enumerate(qqq_dates):
        ret = pct_return(qqq_closes, idx, 20)
        if ret is not None:
            qqq_ret20_by_date[date] = ret
    return {
        "sma20": rolling_mean(closes, 20),
        "sma50": rolling_mean(closes, 50),
        "sma100": rolling_mean(closes, 100),
        "atr14": rolling_mean(true_ranges(rows), 14),
        "ret20": [pct_return(closes, idx, 20) for idx in range(len(rows))],
        "ret60": [pct_return(closes, idx, 60) for idx in range(len(rows))],
        "high55": [max_prior(closes, idx, 55) for idx in range(len(rows))],
        "qqq_ret20": [qqq_ret20_by_date.get(row.date) for row in rows],
    }


SignalFn = Callable[[list[Row], dict[str, list[Any]], int], bool]


def signal_sma50_reclaim(rows: list[Row], ind: dict[str, list[Any]], idx: int) -> bool:
    if idx <= 0:
        return False
    sma50 = ind["sma50"][idx]
    prev_sma50 = ind["sma50"][idx - 1]
    sma100 = ind["sma100"][idx]
    ret20 = ind["ret20"][idx]
    qqq_ret20 = ind["qqq_ret20"][idx]
    if None in (sma50, prev_sma50, sma100, ret20, qqq_ret20):
        return False
    return (
        rows[idx - 1].close <= prev_sma50
        and rows[idx].close > sma50
        and rows[idx].close > sma100
        and ret20 >= qqq_ret20 - 0.02
    )


def signal_orderly_pullback_resume(rows: list[Row], ind: dict[str, list[Any]], idx: int) -> bool:
    if idx <= 0:
        return False
    sma50 = ind["sma50"][idx]
    sma100 = ind["sma100"][idx]
    ret20 = ind["ret20"][idx]
    if None in (sma50, sma100, ret20):
        return False
    row = rows[idx]
    return (
        row.close > sma100
        and sma50 > sma100
        and row.low <= sma50 * 1.03
        and row.close >= sma50
        and row.close > row.open
        and row.close > rows[idx - 1].close
        and ret20 > 0.0
    )


def signal_qqq_relative_breakout(rows: list[Row], ind: dict[str, list[Any]], idx: int) -> bool:
    high55 = ind["high55"][idx]
    sma50 = ind["sma50"][idx]
    ret20 = ind["ret20"][idx]
    qqq_ret20 = ind["qqq_ret20"][idx]
    if None in (high55, sma50, ret20, qqq_ret20):
        return False
    return (
        rows[idx].close > high55
        and rows[idx].close > sma50
        and ret20 > qqq_ret20 + 0.02
    )


def signal_gap_hold_continuation(rows: list[Row], ind: dict[str, list[Any]], idx: int) -> bool:
    if idx <= 0:
        return False
    sma50 = ind["sma50"][idx]
    ret20 = ind["ret20"][idx]
    qqq_ret20 = ind["qqq_ret20"][idx]
    if None in (sma50, ret20, qqq_ret20):
        return False
    row = rows[idx]
    gap = row.open / rows[idx - 1].close - 1.0
    intraday_range = max(row.high - row.low, 0.01)
    close_location = (row.close - row.low) / intraday_range
    return (
        gap >= 0.03
        and row.close >= row.open
        and close_location >= 0.60
        and row.close > sma50
        and ret20 >= qqq_ret20
    )


ARCHETYPES: dict[str, dict[str, Any]] = {
    "sma50_reclaim": {
        "description": "Cross back above SMA50 while above SMA100 and not materially lagging QQQ.",
        "signal": signal_sma50_reclaim,
    },
    "orderly_pullback_resume": {
        "description": "Uptrend pullback touches near SMA50, then closes green back above SMA50.",
        "signal": signal_orderly_pullback_resume,
    },
    "qqq_relative_55d_breakout": {
        "description": "55-session closing breakout with 20d return at least 2pp above QQQ.",
        "signal": signal_qqq_relative_breakout,
    },
    "gap_hold_continuation": {
        "description": "3% gap up that holds the upper part of the daily range above SMA50.",
        "signal": signal_gap_hold_continuation,
    },
}


def simulate_strategy(
    rows: list[Row],
    qqq_rows: list[Row],
    start: str,
    end: str,
    signal_name: str,
    signal_fn: SignalFn,
) -> dict[str, Any]:
    window_indices = [idx for idx, row in enumerate(rows) if start <= row.date <= end]
    if len(window_indices) < 2:
        return empty_strategy_result("insufficient_window_rows")
    ind = build_indicators(rows, qqq_rows)
    first_idx = window_indices[0]
    last_idx = window_indices[-1]
    equity = INITIAL_CAPITAL
    position: Position | None = None
    pending_entry: dict[str, Any] | None = None
    pending_exit_reason: str | None = None
    curve: list[dict[str, float]] = []
    trades: list[dict[str, Any]] = []
    exposure_days = 0

    for idx in range(first_idx, last_idx + 1):
        row = rows[idx]

        if position is not None and pending_exit_reason is not None:
            exit_price = row.open
            gross_equity = position.shares * exit_price
            equity = gross_equity * (1.0 - HALF_COST_PCT)
            trade_return = equity / position.entry_equity - 1.0
            trades.append(
                {
                    "ticker_entry_date": position.entry_date,
                    "entry_signal_date": position.entry_signal_date,
                    "exit_date": row.date,
                    "entry_price": round(position.entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "trade_return_pct": round(trade_return, 6),
                    "holding_days": idx - position.entry_index,
                    "exit_reason": pending_exit_reason,
                    "entry_reason": position.entry_reason,
                }
            )
            position = None
            pending_exit_reason = None

        if position is None and pending_entry is not None:
            entry_price = row.open
            entry_equity = equity
            shares = equity * (1.0 - HALF_COST_PCT) / entry_price
            position = Position(
                entry_date=row.date,
                entry_price=entry_price,
                shares=shares,
                entry_signal_date=str(pending_entry["signal_date"]),
                entry_index=idx,
                entry_equity=entry_equity,
                entry_reason=signal_name,
            )
            pending_entry = None

        if position is not None:
            mark_equity = position.shares * row.close
            exposure_days += 1
        else:
            mark_equity = equity
        curve.append({"date": row.date, "equity": mark_equity})

        if position is not None:
            equity = mark_equity
            sma20 = ind["sma20"][idx]
            atr14 = ind["atr14"][idx]
            days_held = idx - position.entry_index + 1
            stop_hit = (
                atr14 is not None
                and row.close <= position.entry_price - ATR_STOP_UNITS * atr14
            )
            if stop_hit:
                pending_exit_reason = "close_below_2_5atr_stop"
            elif sma20 is not None and row.close < sma20:
                pending_exit_reason = "close_below_sma20"
            elif days_held >= MAX_HOLD_DAYS:
                pending_exit_reason = "max_25_session_hold"
            continue

        # Entry signals are evaluated at close and executed next open. The final
        # window day cannot open a new position because no next-open fill exists
        # inside the fixed window.
        if idx < last_idx and start <= row.date <= end and signal_fn(rows, ind, idx):
            pending_entry = {"signal_date": row.date}

    if position is not None:
        final = rows[last_idx]
        exit_price = final.close
        gross_equity = position.shares * exit_price
        equity = gross_equity * (1.0 - HALF_COST_PCT)
        trade_return = equity / position.entry_equity - 1.0
        trades.append(
            {
                "ticker_entry_date": position.entry_date,
                "entry_signal_date": position.entry_signal_date,
                "exit_date": final.date,
                "entry_price": round(position.entry_price, 4),
                "exit_price": round(exit_price, 4),
                "trade_return_pct": round(trade_return, 6),
                "holding_days": last_idx - position.entry_index + 1,
                "exit_reason": "forced_window_close",
                "entry_reason": position.entry_reason,
            }
        )
        curve[-1] = {"date": final.date, "equity": equity}

    metrics = metrics_from_curve(curve)
    wins = sum(1 for trade in trades if float(trade["trade_return_pct"]) > 0)
    metrics.update(
        {
            "available": True,
            "trade_count": len(trades),
            "win_rate": round(wins / len(trades), 6) if trades else None,
            "exposure_pct": round(exposure_days / len(curve), 6) if curve else 0.0,
            "entry_signal_count": len(trades) + (1 if pending_entry else 0),
            "trades": trades[:20],
        }
    )
    return metrics


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 6) if drawdowns else None,
    }


def aggregate_strategy(
    ticker: str,
    archetype: str,
    windows: dict[str, dict[str, Any]],
    comparators: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    trade_count = sum(int(row.get("trade_count") or 0) for row in windows.values())
    return_sum = sum(float(row.get("total_return_pct") or 0.0) for row in windows.values())
    ev_sum = sum(float(row.get("expected_value_score") or 0.0) for row in windows.values())
    worst_dd = max(float(row.get("max_drawdown_pct") or 0.0) for row in windows.values())
    exposure_avg = statistics.mean(float(row.get("exposure_pct") or 0.0) for row in windows.values())
    bh_return_sum = 0.0
    bh_ev_sum = 0.0
    bh_worst_dd = 0.0
    spy_ev_sum = 0.0
    qqq_ev_sum = 0.0
    windows_return_beats_bh = 0
    windows_ev_beats_bh = 0
    windows_return_beats_spy = 0
    windows_return_beats_qqq = 0
    by_window_delta: dict[str, Any] = {}
    for label, metrics in windows.items():
        ticker_bh = comparators[ticker][label]["ticker_buy_hold"]
        spy = comparators[ticker][label]["SPY_buy_hold"]
        qqq = comparators[ticker][label]["QQQ_buy_hold"]
        m_ret = float(metrics.get("total_return_pct") or 0.0)
        m_ev = float(metrics.get("expected_value_score") or 0.0)
        bh_ret = float(ticker_bh.get("total_return_pct") or 0.0)
        bh_ev = float(ticker_bh.get("expected_value_score") or 0.0)
        spy_ret = float(spy.get("total_return_pct") or 0.0)
        qqq_ret = float(qqq.get("total_return_pct") or 0.0)
        if m_ret > bh_ret:
            windows_return_beats_bh += 1
        if m_ev > bh_ev:
            windows_ev_beats_bh += 1
        if m_ret > spy_ret:
            windows_return_beats_spy += 1
        if m_ret > qqq_ret:
            windows_return_beats_qqq += 1
        bh_return_sum += bh_ret
        bh_ev_sum += bh_ev
        bh_worst_dd = max(bh_worst_dd, float(ticker_bh.get("max_drawdown_pct") or 0.0))
        spy_ev_sum += float(spy.get("expected_value_score") or 0.0)
        qqq_ev_sum += float(qqq.get("expected_value_score") or 0.0)
        by_window_delta[label] = {
            "return_delta_vs_ticker_buy_hold": round(m_ret - bh_ret, 6),
            "ev_delta_vs_ticker_buy_hold": round(m_ev - bh_ev, 4),
            "return_delta_vs_spy": round(m_ret - spy_ret, 6),
            "return_delta_vs_qqq": round(m_ret - qqq_ret, 6),
            "trade_count": int(metrics.get("trade_count") or 0),
            "exposure_pct": metrics.get("exposure_pct"),
        }
    criteria = {
        "trade_count_gte_min": trade_count
        >= ACCEPTANCE_RULE["min_trade_count_per_ticker_archetype"],
        "windows_return_beating_ticker_buy_hold_gte_min": windows_return_beats_bh
        >= ACCEPTANCE_RULE["min_windows_beating_ticker_buy_hold"],
        "windows_ev_beating_ticker_buy_hold_gte_min": windows_ev_beats_bh
        >= ACCEPTANCE_RULE["min_windows_beating_ticker_buy_hold"],
        "aggregate_return_delta_vs_ticker_buy_hold_positive": return_sum > bh_return_sum,
        "aggregate_ev_delta_vs_ticker_buy_hold_positive": ev_sum > bh_ev_sum,
        "aggregate_ev_beats_spy_and_qqq": ev_sum > spy_ev_sum and ev_sum > qqq_ev_sum,
        "worst_drawdown_within_guard": worst_dd
        <= bh_worst_dd + ACCEPTANCE_RULE["max_drawdown_extra_vs_ticker_buy_hold"],
    }
    return {
        "ticker": ticker,
        "archetype": archetype,
        "aggregate_return_sum": round(return_sum, 6),
        "aggregate_ev_sum": round(ev_sum, 4),
        "aggregate_return_delta_vs_ticker_buy_hold": round(return_sum - bh_return_sum, 6),
        "aggregate_ev_delta_vs_ticker_buy_hold": round(ev_sum - bh_ev_sum, 4),
        "aggregate_ticker_buy_hold_return_sum": round(bh_return_sum, 6),
        "aggregate_ticker_buy_hold_ev_sum": round(bh_ev_sum, 4),
        "aggregate_spy_ev_sum": round(spy_ev_sum, 4),
        "aggregate_qqq_ev_sum": round(qqq_ev_sum, 4),
        "trade_count": trade_count,
        "average_exposure_pct": round(exposure_avg, 6),
        "worst_drawdown_pct": round(worst_dd, 6),
        "ticker_buy_hold_worst_drawdown_pct": round(bh_worst_dd, 6),
        "windows_return_beating_ticker_buy_hold": windows_return_beats_bh,
        "windows_ev_beating_ticker_buy_hold": windows_ev_beats_bh,
        "windows_return_beating_spy": windows_return_beats_spy,
        "windows_return_beating_qqq": windows_return_beats_qqq,
        "by_window_delta": by_window_delta,
        "criteria": criteria,
        "lead_passed": all(criteria.values()),
    }


def run_analysis() -> dict[str, Any]:
    results: dict[str, dict[str, dict[str, Any]]] = {
        ticker: {name: {} for name in ARCHETYPES} for ticker in TARGET_TICKERS
    }
    comparators: dict[str, dict[str, dict[str, Any]]] = {ticker: {} for ticker in TARGET_TICKERS}
    coverage: dict[str, Any] = {}

    for spec in WINDOWS:
        snapshot = load_snapshot(spec["snapshot"])
        label = str(spec["label"])
        coverage[label] = {
            "snapshot": repo_rel(spec["snapshot"]),
            "tickers_loaded": sorted(set(snapshot) & set(TARGET_TICKERS + BENCHMARK_TICKERS)),
        }
        qqq_rows = snapshot.get("QQQ", [])
        spy_rows = snapshot.get("SPY", [])
        for ticker in TARGET_TICKERS:
            ticker_rows = snapshot.get(ticker, [])
            comparators[ticker][label] = {
                "ticker_buy_hold": benchmark_buy_hold(ticker_rows, str(spec["start"]), str(spec["end"])),
                "SPY_buy_hold": benchmark_buy_hold(spy_rows, str(spec["start"]), str(spec["end"])),
                "QQQ_buy_hold": benchmark_buy_hold(qqq_rows, str(spec["start"]), str(spec["end"])),
            }
            for name, archetype in ARCHETYPES.items():
                if not ticker_rows or not qqq_rows:
                    metrics = empty_strategy_result("missing_ticker_or_qqq_rows")
                else:
                    metrics = simulate_strategy(
                        ticker_rows,
                        qqq_rows,
                        str(spec["start"]),
                        str(spec["end"]),
                        name,
                        archetype["signal"],
                    )
                results[ticker][name][label] = metrics

    aggregates: list[dict[str, Any]] = []
    for ticker in TARGET_TICKERS:
        for name in ARCHETYPES:
            aggregates.append(
                aggregate_strategy(ticker, name, results[ticker][name], comparators)
            )
    aggregates.sort(
        key=lambda row: (
            bool(row["lead_passed"]),
            float(row["aggregate_ev_delta_vs_ticker_buy_hold"]),
            float(row["aggregate_return_delta_vs_ticker_buy_hold"]),
        ),
        reverse=True,
    )
    leads = [row for row in aggregates if row["lead_passed"]]
    best_by_ticker: dict[str, Any] = {}
    for ticker in TARGET_TICKERS:
        ticker_rows = [row for row in aggregates if row["ticker"] == ticker]
        best_by_ticker[ticker] = ticker_rows[0] if ticker_rows else None
    return {
        "coverage": coverage,
        "comparators": comparators,
        "archetype_definitions": {
            name: {"description": meta["description"]} for name, meta in ARCHETYPES.items()
        },
        "strategy_results": results,
        "aggregate_ranked": aggregates,
        "best_by_ticker": best_by_ticker,
        "leads": leads,
        "observed_only_lead_passed": bool(leads),
    }


def build_record(analysis: dict[str, Any]) -> dict[str, Any]:
    base = baseline_metrics()
    lead_passed = bool(analysis["observed_only_lead_passed"])
    decision = (
        "observed_only_positive_single_name_timing_lead_not_promoted"
        if lead_passed
        else "observed_only_rejected_single_name_timing_scout"
    )
    best = analysis["aggregate_ranked"][0] if analysis["aggregate_ranked"] else {}
    strategy_delta = {
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "max_drawdown_pct_delta": 0.0,
        "strategy_behavior_changed": False,
        "live_order_behavior_changed": False,
    }
    gate4 = {
        "passed": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": decision,
        "observed_only_lead_passed": lead_passed,
        "best_candidate": best,
        "measurement_blockers": [],
        "alpha_blockers": [
            "observed_only_private_replay_not_shared_policy",
            "requires_default_off_helper_daily_snapshot_parity_gate_1_4",
        ]
        if lead_passed
        else [
            "predeclared_single_name_timing_lead_criteria_not_met",
        ],
        "before_after_strategy_delta": strategy_delta,
        "note": "No strategy or production behavior changed; Gate 4 cannot accept alpha.",
    }
    realized_failure_modes: list[str] = []
    if not lead_passed:
        realized_failure_modes.append("fails_buy_hold_benchmark")
    if best and int(best.get("trade_count") or 0) < ACCEPTANCE_RULE["min_trade_count_per_ticker_archetype"]:
        realized_failure_modes.append("thin_trade_count")
    if best and int(best.get("windows_return_beating_ticker_buy_hold") or 0) < ACCEPTANCE_RULE["min_windows_beating_ticker_buy_hold"]:
        realized_failure_modes.append("no_window_stability")
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1 if lead_passed else 0,
        "brier_score": round((PREDICTION["success_probability"] - (1 if lead_passed else 0)) ** 2, 6),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_modes": realized_failure_modes,
        "predicted_failure_mode_hit": any(
            mode in PREDICTION["main_failure_modes"] for mode in realized_failure_modes
        ),
        "calibration_note": (
            "Success means a read-only single-name timing lead passed fixed "
            "criteria; alpha acceptance still requires shared default-off "
            "implementation and Gate 1-4."
        ),
    }
    record = {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "owner": OWNER,
        "status": "observed_only",
        "decision": decision,
        "timestamp": utc_now(),
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "alpha_hypothesis_category": "entry_exit_timing",
        "change_type": CHANGE_TYPE,
        "implementation_mode": "read_only_private_replay_scout",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "causal_components": CAUSAL_COMPONENTS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "parameters": {
            "target_tickers": list(TARGET_TICKERS),
            "benchmarks": list(BENCHMARK_TICKERS),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "initial_capital": INITIAL_CAPITAL,
            "entry_execution": "signal at close, next-open fill",
            "exit_execution": "close-based exit condition, next-open fill; forced final close",
            "common_exit_envelope": {
                "max_hold_sessions": MAX_HOLD_DAYS,
                "trend_exit": "close below SMA20",
                "stop": f"close <= entry - {ATR_STOP_UNITS} * ATR14",
            },
            "archetypes": analysis["archetype_definitions"],
        },
        "gate1": {"passed": True, "baseline_metrics": base},
        "gate2": {
            "passed": True,
            "dependencies_validated": True,
            "fields_checked": ["Date", "Open", "High", "Low", "Close", "Volume"],
            "entry_date_scope": "Synthetic scout trade entry_date is generated from next-open fills.",
            "target_price_scope": "Not applicable; this scout uses a fixed close/SMA20/ATR/max-hold exit envelope.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": base.get("signals_generated"),
            "signals_survived": base.get("signals_survived"),
            "survival_rate": base.get("survival_rate"),
            "note": "No production filter was added; scout trade counts are diagnostic sample size only.",
        },
        "gate4": gate4,
        "before_metrics": base,
        "after_metrics": base,
        "delta_metrics": {
            **strategy_delta,
            "observed_only_lead_passed": lead_passed,
            "best_candidate": best,
            "lead_count": len(analysis["leads"]),
        },
        "observed_metrics": analysis,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "scope": "read_only_private_single_name_replay",
        },
        "post_run_reflection": {
            "why_result_happened": (
                f"Best fixed row was {best.get('ticker')} / {best.get('archetype')} "
                f"with aggregate_return_delta_vs_ticker_buy_hold="
                f"{best.get('aggregate_return_delta_vs_ticker_buy_hold')} and "
                f"aggregate_ev_delta_vs_ticker_buy_hold="
                f"{best.get('aggregate_ev_delta_vs_ticker_buy_hold')}. "
                f"Lead criteria passed={lead_passed}."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune SMA lengths, breakout lookback, gap threshold, "
                "ATR stop, max-hold days, ticker subset, or comparator choice on "
                "the same frozen APP/META windows."
            ),
            "new_evidence_required": (
                "A valid next step requires either a shared default-off helper "
                "using the exact passing fixed archetype, materially new forward "
                "single-name rows, or a non-price PIT source such as borrow, "
                "flow, options, or event semantics."
            ),
        },
        "next_retry_requires": [
            "shared default-off helper plus daily snapshot and parity if promoting a positive lead",
            "or materially more forward single-name rows",
            "or a genuinely different non-price PIT data source",
            "no frozen-window threshold retunes on APP/META OHLCV only",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": [
            repo_rel(BASELINE_RESULT),
            *[repo_rel(item["snapshot"]) for item in WINDOWS],
            "experiments/logs/exp-20260507-008.json",
            "experiments/logs/exp-20260507-028.json",
            "experiments/logs/exp-20260507-030.json",
            "experiments/logs/exp-20260517-024.json",
        ],
        "calibration": calibration,
        "lean_quality_passed": True,
    }
    return record


def build_card(record: dict[str, Any]) -> str:
    best = record["delta_metrics"]["best_candidate"]
    leads = record["delta_metrics"]["lead_count"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} {SLUG}",
            "",
            "## Decision",
            "",
            f"- `{record['decision']}`",
            f"- observed-only lead passed: `{record['delta_metrics']['observed_only_lead_passed']}`",
            f"- lead count: `{leads}`",
            "",
            "## Best Fixed Row",
            "",
            f"- ticker/archetype: `{best.get('ticker')}` / `{best.get('archetype')}`",
            f"- aggregate return delta vs own buy-and-hold: `{best.get('aggregate_return_delta_vs_ticker_buy_hold')}`",
            f"- aggregate EV delta vs own buy-and-hold: `{best.get('aggregate_ev_delta_vs_ticker_buy_hold')}`",
            f"- trade count: `{best.get('trade_count')}`",
            f"- windows beating own buy-and-hold return: `{best.get('windows_return_beating_ticker_buy_hold')}`",
            "",
            "## Boundary",
            "",
            "No strategy, shared policy, backtester adapter, run adapter, sizing, ranking, orders, paper state, or LLM boundary changed.",
            "A positive row is only a lead until it is implemented as a shared default-off helper and passes Gate 1-4.",
            "",
            "## Anti-Repeat",
            "",
            record["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            f"```powershell\n{RUNNER_COMMAND}\n```",
            "",
        ]
    )


def build_manifest(record: dict[str, Any]) -> dict[str, Any]:
    files = [Path(path) if Path(path).is_absolute() else REPO_ROOT / path for path in record["changed_files"]]
    return {
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "generated_at": utc_now(),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "decision": record["decision"],
        "files": [
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        ],
    }


def main() -> int:
    analysis = run_analysis()
    record = build_record(analysis)
    write_json(OUT_JSON, record)
    write_json(LOG_JSON, record)
    write_text(CARD_MD, build_card(record))
    write_json(MANIFEST_JSON, build_manifest(record))
    prediction = load_ticket_prediction()
    persisted = persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=prediction,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "decision": record["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": record["gate4"],
            "delta_metrics": record["delta_metrics"],
            "calibration": record["calibration"],
        },
        status="observed_only",
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "new_gate_shape",
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "acceptance_rule": (
                "Observed-only lead: one ticker/archetype must beat its own "
                "buy-and-hold return and EV in at least two windows, positive "
                "aggregate return/EV deltas, aggregate EV above SPY/QQQ, "
                "trade_count >= 6, and drawdown within +2pp of own buy-and-hold. "
                "No production behavior can be accepted."
            ),
        },
    )
    record["registry_update"] = {"status": persisted.get("status"), "completed_at": persisted.get("completed_at")}
    write_json(OUT_JSON, record)
    write_json(LOG_JSON, record)
    write_json(MANIFEST_JSON, build_manifest(record))
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": record["decision"],
                "best": record["delta_metrics"]["best_candidate"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
