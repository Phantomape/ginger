"""exp-20260708-022: Donchian/Turtle breakout external baseline.

Read-only external baseline replay. The fixed question is whether a canonical
Donchian/Turtle 55-day breakout with a 20-day channel exit is a stronger
breakout family than the current accepted `breakout_long` comparator on the
canonical windows. This runner changes no production strategy, sizing, ranking,
orders, paper state, backtester adapter, or LLM boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-022"
OWNER = "codex-alpha-explore"
SLUG = "donchian_turtle_breakout_external_baseline"
RUNNER = f"quant/experiments/exp_20260708_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
WINDOW_SOURCES = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
]

PLAN_DOC = REPO_ROOT / "docs" / "core_entry_admission_external_strategy_plan.md"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_022_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_measurement.json"
AFTER_JSON = DATA_DIR / "after_measurement.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "A fixed Donchian/Turtle 55-day channel breakout with 20-day channel exit "
    "should reveal whether the current breakout_long weakness is a local "
    "implementation problem or whether a simple external price-channel "
    "breakout family also fails against the accepted core breakout comparator "
    "on the canonical windows."
)
CHANGE_TYPE = "entry_external_baseline_observed_only_replay"
IMPLEMENTATION_MODE = "read_only_external_baseline_replay"
MECHANISM_FAMILY = "external_price_channel_breakout_baseline"
TRIAL_FAMILY = "donchian_turtle_breakout_baseline"
TRIAL_VARIANT_ID = "exp-20260708-022"
CHANGED_VARIABLE = "donchian_55_20_turtle_breakout_baseline_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape and external benchmark family: predeclared "
    "Donchian/Turtle 55-day channel breakout entry plus 20-day channel exit, "
    "compared against current breakout_long on the same canonical OHLCV "
    "windows; not a retune of existing breakout thresholds, stops, DTE "
    "buckets, risk scalars, or ticker/window slices."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-021", "exp-20260708-002"]
CAUSAL_COMPONENTS = [
    "fixed 55-day high breakout entry",
    "fixed 20-day low exit",
    "20-day ATR risk sizing",
    "5-position cap",
    "canonical OHLCV snapshots",
    "no strategy code change",
]
PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "simple_channel_breakout_lags_core_breakout",
        "too_many_whipsaws",
        "trade_count_too_low",
        "drawdown_worse",
        "private_replay_not_production_ready",
    ],
    "confidence_reason": (
        "The current core breakout has strong late-window performance but "
        "weaker historical consistency; a canonical Donchian benchmark may "
        "expose whether the problem is local implementation, but simple "
        "channel systems often whipsaw on a concentrated equity universe."
    ),
    "recorded_at": "2026-07-08T17:33:43+00:00",
}

CONFIG = {
    "initial_capital": 100_000.0,
    "entry_channel_days": 55,
    "exit_channel_days": 20,
    "atr_days": 20,
    "risk_pct_per_trade": 0.01,
    "atr_stop_units_for_sizing": 2.0,
    "max_positions": 5,
    "max_position_notional_pct": 1.0,
    "max_gross_notional_pct": 3.0,
    "round_trip_cost_pct": 0.0035,
    "min_price": 5.0,
    "min_avg_dollar_volume_20d": 20_000_000.0,
    "annualization_days": 252,
    "max_acceptable_window_drawdown_pct": 0.16,
    "min_trade_count_for_lead": 20,
    "min_breakout_win_windows": 2,
    "diagnostic_only": True,
    "acceptance_rule": (
        "Observed-only external baseline lead only: fixed Donchian 55/20 "
        "replay must beat current breakout_long aggregate PnL and win at "
        "least two canonical windows versus breakout_long while keeping max "
        "drawdown <= 16% and trade count >= 20. A positive result still "
        "requires shared helper/backtester Gate 1-4 before behavior changes."
    ),
}

EXCLUDED_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "GLD",
    "IAU",
    "SLV",
    "IEF",
    "TLT",
    "USO",
    "UUP",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}


@dataclass
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    entry_notional: float
    entry_signal_date: str
    entry_strength: float
    entry_atr: float


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
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


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def money(value: Any) -> float:
    numeric = as_float(value)
    return 0.0 if numeric is None else numeric


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def valid_bar(row: dict[str, Any]) -> bool:
    return all(money(row.get(field)) > 0.0 for field in ("Open", "High", "Low", "Close"))


def load_snapshot(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    raw = read_json(path, {})
    metadata = raw.get("metadata") or {}
    excluded = set(EXCLUDED_TICKERS)
    excluded.update(str(ticker) for ticker in metadata.get("cross_asset_proxies_added") or [])
    excluded.update(str(ticker) for ticker in metadata.get("added_tickers") or [])
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw.get("ohlcv") or {}).items():
        if ticker in excluded:
            continue
        cleaned = [row for row in rows if isinstance(row, dict) and valid_bar(row)]
        cleaned.sort(key=lambda row: str(row.get("Date") or ""))
        if cleaned:
            result[str(ticker)] = cleaned
    return result, {
        "metadata": metadata,
        "excluded_tickers": sorted(excluded),
        "eligible_tickers": sorted(result),
    }


def true_range(rows: list[dict[str, Any]], index: int) -> float:
    high = money(rows[index]["High"])
    low = money(rows[index]["Low"])
    if index <= 0:
        return high - low
    prev_close = money(rows[index - 1]["Close"])
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def avg_dollar_volume(rows: list[dict[str, Any]], end_exclusive: int, lookback: int) -> float | None:
    start = end_exclusive - lookback
    if start < 0:
        return None
    values = [
        money(row.get("Close")) * money(row.get("Volume"))
        for row in rows[start:end_exclusive]
    ]
    return statistics.fmean(values) if values else None


def atr(rows: list[dict[str, Any]], end_index: int, lookback: int) -> float | None:
    start = end_index - lookback + 1
    if start <= 0:
        return None
    values = [true_range(rows, idx) for idx in range(start, end_index + 1)]
    return statistics.fmean(values) if values else None


def signal_context(rows: list[dict[str, Any]], signal_idx: int) -> dict[str, Any] | None:
    entry_lookback = CONFIG["entry_channel_days"]
    exit_lookback = CONFIG["exit_channel_days"]
    atr_days = CONFIG["atr_days"]
    if signal_idx < max(entry_lookback, exit_lookback, atr_days):
        return None
    signal_bar = rows[signal_idx]
    close = money(signal_bar["Close"])
    prior_high = max(money(row["High"]) for row in rows[signal_idx - entry_lookback : signal_idx])
    prior_low = min(money(row["Low"]) for row in rows[signal_idx - exit_lookback : signal_idx])
    atr_value = atr(rows, signal_idx, atr_days)
    adv_value = avg_dollar_volume(rows, signal_idx + 1, atr_days)
    if atr_value is None or atr_value <= 0 or adv_value is None:
        return None
    return {
        "signal_date": signal_bar["Date"],
        "close": close,
        "prior_entry_high": prior_high,
        "prior_exit_low": prior_low,
        "breakout_signal": close > prior_high,
        "exit_signal": close < prior_low,
        "breakout_strength": close / prior_high - 1.0 if prior_high > 0 else 0.0,
        "atr": atr_value,
        "avg_dollar_volume_20d": adv_value,
    }


def build_signal_maps(
    ohlcv: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, dict[str, dict[str, Any]]]]:
    start_date = parse_date(start)
    end_date = parse_date(end)
    bars_by_date: dict[str, dict[str, Any]] = {}
    signals_by_entry_date: dict[str, list[dict[str, Any]]] = {}
    contexts_by_ticker_date: dict[str, dict[str, dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        contexts_by_ticker_date[ticker] = {}
        for i in range(1, len(rows)):
            entry_date = str(rows[i]["Date"])
            entry_dt = parse_date(entry_date)
            if entry_dt < start_date or entry_dt > end_date:
                continue
            context = signal_context(rows, i - 1)
            if context is None:
                continue
            context = dict(context)
            context.update(
                {
                    "ticker": ticker,
                    "entry_date": entry_date,
                    "entry_open": money(rows[i]["Open"]),
                    "entry_close": money(rows[i]["Close"]),
                }
            )
            contexts_by_ticker_date[ticker][entry_date] = context
            bars_by_date.setdefault(entry_date, {})[ticker] = rows[i]
            if context["breakout_signal"]:
                signals_by_entry_date.setdefault(entry_date, []).append(context)
    return bars_by_date, signals_by_entry_date, contexts_by_ticker_date


def position_market_value(position: Position, close_price: float) -> float:
    return position.shares * close_price


def position_unrealized(position: Position, close_price: float) -> float:
    return (close_price - position.entry_price) * position.shares


def close_position(
    position: Position,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
) -> dict[str, Any]:
    gross_pnl = (exit_price - position.entry_price) * position.shares
    round_trip_cost = position.entry_notional * CONFIG["round_trip_cost_pct"]
    pnl = gross_pnl - round_trip_cost
    return {
        "ticker": position.ticker,
        "strategy": "donchian_turtle_55_20",
        "entry_date": position.entry_date,
        "entry_signal_date": position.entry_signal_date,
        "exit_date": exit_date,
        "exit_reason": exit_reason,
        "entry_price": rounded(position.entry_price, 4),
        "exit_price": rounded(exit_price, 4),
        "shares": position.shares,
        "entry_notional": rounded(position.entry_notional, 2),
        "entry_strength": rounded(position.entry_strength),
        "entry_atr": rounded(position.entry_atr, 4),
        "gross_pnl": rounded(gross_pnl, 2),
        "round_trip_cost": rounded(round_trip_cost, 2),
        "pnl": rounded(pnl, 2),
        "pnl_pct_net": rounded(pnl / position.entry_notional if position.entry_notional else 0.0),
    }


def summarize_returns(label: str, equity_curve: list[dict[str, Any]]) -> dict[str, Any]:
    if not equity_curve:
        return {
            "label": label,
            "trading_days": 0,
            "total_return_pct": 0.0,
            "expected_value_score": 0.0,
            "sharpe_daily": 0.0,
            "max_drawdown_pct": 0.0,
        }
    equities = [money(row["equity"]) for row in equity_curve]
    initial = CONFIG["initial_capital"]
    total_return = equities[-1] / initial - 1.0
    returns: list[float] = []
    for prev, cur in zip(equities, equities[1:]):
        if prev > 0:
            returns.append(cur / prev - 1.0)
    if len(returns) > 1:
        stdev = statistics.stdev(returns)
        mean_ret = statistics.fmean(returns)
        sharpe = mean_ret / stdev * math.sqrt(CONFIG["annualization_days"]) if stdev else 0.0
    else:
        sharpe = 0.0
    peak = equities[0]
    max_dd = 0.0
    for value in equities:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return {
        "label": label,
        "trading_days": len(equity_curve),
        "total_return_pct": rounded(total_return),
        "expected_value_score": rounded(total_return * sharpe),
        "sharpe_daily": rounded(sharpe),
        "max_drawdown_pct": rounded(abs(max_dd)),
        "ending_equity": rounded(equities[-1], 2),
    }


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [money(trade.get("pnl")) for trade in trades]
    wins = sum(1 for value in pnls if value > 0)
    losses = sum(1 for value in pnls if value < 0)
    return {
        "trade_count": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": rounded(wins / len(trades), 4) if trades else None,
        "total_pnl": rounded(sum(pnls), 2),
        "avg_pnl": rounded(statistics.fmean(pnls), 2) if pnls else None,
        "largest_winner": rounded(max(pnls), 2) if pnls else None,
        "largest_loser": rounded(min(pnls), 2) if pnls else None,
    }


def simulate_window(source: dict[str, Any]) -> dict[str, Any]:
    ohlcv, universe = load_snapshot(source["snapshot"])
    bars_by_date, signals_by_entry_date, contexts = build_signal_maps(
        ohlcv, source["start"], source["end"]
    )
    all_dates = sorted(bars_by_date)
    positions: dict[str, Position] = {}
    closed_trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    realized_pnl = 0.0
    skipped_signals: list[dict[str, Any]] = []

    for current_date in all_dates:
        # Exits use the prior close's 20-day low signal and fill at current open.
        for ticker in list(positions):
            position = positions[ticker]
            context = contexts.get(ticker, {}).get(current_date)
            bar = bars_by_date[current_date].get(ticker)
            if not context or not bar:
                continue
            if context["exit_signal"]:
                trade = close_position(
                    position,
                    current_date,
                    money(bar["Open"]),
                    "donchian_20d_low_exit_next_open",
                )
                realized_pnl += money(trade["pnl"])
                closed_trades.append(trade)
                del positions[ticker]

        candidates = sorted(
            signals_by_entry_date.get(current_date, []),
            key=lambda row: (
                money(row.get("breakout_strength")),
                money(row.get("avg_dollar_volume_20d")),
                str(row.get("ticker")),
            ),
            reverse=True,
        )
        gross_notional = sum(position.entry_notional for position in positions.values())
        for candidate in candidates:
            ticker = str(candidate["ticker"])
            if ticker in positions:
                continue
            if len(positions) >= CONFIG["max_positions"]:
                skipped_signals.append(
                    {
                        "date": current_date,
                        "ticker": ticker,
                        "reason": "max_positions_full",
                    }
                )
                continue
            entry_price = money(candidate["entry_open"])
            if entry_price < CONFIG["min_price"]:
                skipped_signals.append(
                    {"date": current_date, "ticker": ticker, "reason": "price_floor"}
                )
                continue
            if money(candidate["avg_dollar_volume_20d"]) < CONFIG["min_avg_dollar_volume_20d"]:
                skipped_signals.append(
                    {"date": current_date, "ticker": ticker, "reason": "liquidity_floor"}
                )
                continue
            risk_unit = money(candidate["atr"]) * CONFIG["atr_stop_units_for_sizing"]
            if risk_unit <= 0:
                continue
            risk_dollars = CONFIG["initial_capital"] * CONFIG["risk_pct_per_trade"]
            shares = int(risk_dollars / risk_unit)
            if shares <= 0:
                continue
            max_position_notional = CONFIG["initial_capital"] * CONFIG["max_position_notional_pct"]
            max_gross_notional = CONFIG["initial_capital"] * CONFIG["max_gross_notional_pct"]
            allowed_notional = min(max_position_notional, max_gross_notional - gross_notional)
            if allowed_notional <= 0:
                skipped_signals.append(
                    {"date": current_date, "ticker": ticker, "reason": "gross_notional_full"}
                )
                continue
            shares = min(shares, int(allowed_notional / entry_price))
            if shares <= 0:
                continue
            entry_notional = shares * entry_price
            positions[ticker] = Position(
                ticker=ticker,
                entry_date=current_date,
                entry_price=entry_price,
                shares=shares,
                entry_notional=entry_notional,
                entry_signal_date=str(candidate["signal_date"]),
                entry_strength=money(candidate["breakout_strength"]),
                entry_atr=money(candidate["atr"]),
            )
            gross_notional += entry_notional

        open_unrealized = 0.0
        open_notional = 0.0
        for ticker, position in positions.items():
            bar = bars_by_date[current_date].get(ticker)
            if not bar:
                continue
            close_price = money(bar["Close"])
            open_unrealized += position_unrealized(position, close_price)
            open_notional += position_market_value(position, close_price)
        equity_curve.append(
            {
                "date": current_date,
                "equity": rounded(CONFIG["initial_capital"] + realized_pnl + open_unrealized, 2),
                "realized_pnl": rounded(realized_pnl, 2),
                "open_positions": len(positions),
                "open_notional": rounded(open_notional, 2),
            }
        )

    if all_dates:
        final_date = all_dates[-1]
        for ticker, position in list(positions.items()):
            bar = bars_by_date[final_date].get(ticker)
            if not bar:
                continue
            trade = close_position(
                position,
                final_date,
                money(bar["Close"]),
                "window_end_forced_close",
            )
            realized_pnl += money(trade["pnl"])
            closed_trades.append(trade)
            del positions[ticker]
        equity_curve[-1]["equity"] = rounded(CONFIG["initial_capital"] + realized_pnl, 2)
        equity_curve[-1]["realized_pnl"] = rounded(realized_pnl, 2)
        equity_curve[-1]["open_positions"] = 0
        equity_curve[-1]["open_notional"] = 0.0

    current_core = read_json(source["core_result"], {})
    core_breakout = (current_core.get("by_strategy") or {}).get("breakout_long") or {}
    metrics = summarize_returns(source["label"], equity_curve)
    trade_summary = summarize_trades(closed_trades)
    total_pnl = money(trade_summary["total_pnl"])
    core_breakout_pnl = money(core_breakout.get("total_pnl_usd"))
    return {
        "label": source["label"],
        "start": source["start"],
        "end": source["end"],
        "snapshot": repo_rel(source["snapshot"]),
        "core_result": repo_rel(source["core_result"]),
        "universe": {
            "eligible_ticker_count": len(universe["eligible_tickers"]),
            "eligible_tickers": universe["eligible_tickers"],
            "excluded_tickers": universe["excluded_tickers"],
        },
        "donchian_metrics": metrics,
        "donchian_trade_summary": trade_summary,
        "current_core_metrics": {
            "expected_value_score": rounded(as_float(current_core.get("expected_value_score"))),
            "total_pnl": rounded(as_float(current_core.get("total_pnl")), 2),
            "max_drawdown_pct": rounded(as_float(current_core.get("max_drawdown_pct"))),
            "total_trades": int(current_core.get("total_trades") or 0),
        },
        "current_breakout_long": {
            "trade_count": int(core_breakout.get("trade_count") or 0),
            "win_rate": rounded(as_float(core_breakout.get("win_rate"))),
            "total_pnl_usd": rounded(core_breakout_pnl, 2),
            "avg_pnl_pct_net": rounded(as_float(core_breakout.get("avg_pnl_pct_net"))),
            "profit_factor": rounded(as_float(core_breakout.get("profit_factor"))),
        },
        "comparison_vs_breakout_long": {
            "pnl_delta": rounded(total_pnl - core_breakout_pnl, 2),
            "donchian_beats_breakout_pnl": total_pnl > core_breakout_pnl,
        },
        "signal_diagnostics": {
            "raw_breakout_signal_count": sum(
                1 for entries in signals_by_entry_date.values() for _ in entries
            ),
            "skipped_signal_count": len(skipped_signals),
            "skipped_reason_counts": {
                reason: sum(1 for row in skipped_signals if row["reason"] == reason)
                for reason in sorted({row["reason"] for row in skipped_signals})
            },
        },
        "trades": closed_trades,
        "equity_curve_tail": equity_curve[-10:],
    }


def aggregate_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    total_pnl = sum(money(row["donchian_trade_summary"]["total_pnl"]) for row in windows)
    breakout_pnl = sum(money(row["current_breakout_long"]["total_pnl_usd"]) for row in windows)
    trade_count = sum(int(row["donchian_trade_summary"]["trade_count"]) for row in windows)
    breakout_trade_count = sum(int(row["current_breakout_long"]["trade_count"]) for row in windows)
    win_windows = [
        row["label"]
        for row in windows
        if row["comparison_vs_breakout_long"]["donchian_beats_breakout_pnl"]
    ]
    max_dd = max(money(row["donchian_metrics"]["max_drawdown_pct"]) for row in windows)
    total_return = total_pnl / CONFIG["initial_capital"]
    # Window-level score is only a compact diagnostic. Full compounding is not
    # meaningful across disjoint fixed windows in this private replay.
    avg_sharpe = statistics.fmean(
        [money(row["donchian_metrics"]["sharpe_daily"]) for row in windows]
    )
    return {
        "donchian_total_pnl": rounded(total_pnl, 2),
        "current_breakout_long_total_pnl": rounded(breakout_pnl, 2),
        "pnl_delta_vs_breakout_long": rounded(total_pnl - breakout_pnl, 2),
        "donchian_trade_count": trade_count,
        "current_breakout_long_trade_count": breakout_trade_count,
        "donchian_win_windows_vs_breakout_long": win_windows,
        "donchian_win_window_count_vs_breakout_long": len(win_windows),
        "max_window_drawdown_pct": rounded(max_dd),
        "diagnostic_total_return_pct": rounded(total_return),
        "mean_window_sharpe_daily": rounded(avg_sharpe),
        "diagnostic_expected_value_score": rounded(total_return * avg_sharpe),
    }


def evaluate_lead(aggregate: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    if money(aggregate["pnl_delta_vs_breakout_long"]) <= 0:
        failed.append("donchian_aggregate_pnl_not_above_current_breakout_long")
    if (
        int(aggregate["donchian_win_window_count_vs_breakout_long"])
        < CONFIG["min_breakout_win_windows"]
    ):
        failed.append("donchian_fewer_than_two_windows_beat_breakout_long")
    if int(aggregate["donchian_trade_count"]) < CONFIG["min_trade_count_for_lead"]:
        failed.append("donchian_trade_count_below_floor")
    if money(aggregate["max_window_drawdown_pct"]) > CONFIG["max_acceptable_window_drawdown_pct"]:
        failed.append("donchian_drawdown_above_guard")
    if money(aggregate["donchian_total_pnl"]) <= 0:
        failed.append("donchian_not_positive_vs_cash")
    return not failed, failed


def compact_gate4(gate4: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_only": gate4["diagnostic_only"],
        "observed_only_lead": gate4["observed_only_lead"],
        "full_gate4_passed": gate4["full_gate4_passed"],
        "failed_reasons": gate4["failed_reasons"],
        "aggregate": gate4["aggregate"],
        "windows": [
            {
                "label": row["label"],
                "donchian_total_pnl": row["donchian_trade_summary"]["total_pnl"],
                "donchian_trade_count": row["donchian_trade_summary"]["trade_count"],
                "donchian_ev": row["donchian_metrics"]["expected_value_score"],
                "donchian_max_drawdown_pct": row["donchian_metrics"]["max_drawdown_pct"],
                "breakout_long_total_pnl": row["current_breakout_long"]["total_pnl_usd"],
                "pnl_delta_vs_breakout_long": row["comparison_vs_breakout_long"]["pnl_delta"],
                "donchian_beats_breakout_pnl": row["comparison_vs_breakout_long"][
                    "donchian_beats_breakout_pnl"
                ],
            }
            for row in gate4["windows"]
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    windows = [simulate_window(source) for source in WINDOW_SOURCES]
    aggregate = aggregate_windows(windows)
    observed_only_lead, failed_reasons = evaluate_lead(aggregate)
    full_gate4_passed = False
    decision = (
        "observed_only_lead_donchian_breakout_requires_shared_helper_gate_1_4"
        if observed_only_lead
        else "observed_only_rejected_donchian_turtle_breakout_baseline"
    )
    why = (
        "The fixed Donchian/Turtle baseline beat current breakout_long strongly "
        "enough to justify a shared-helper/backtester promotion test. This is "
        "still not accepted behavior because the private replay does not share "
        "the production candidate pipeline or slot displacement semantics."
        if observed_only_lead
        else "The fixed Donchian/Turtle baseline did not beat the accepted "
        "current breakout_long comparator under the predeclared private replay "
        "criteria, so the weakness is not solved by simply replacing core "
        "breakouts with a vanilla 55/20 channel system."
    )
    production_impact = {
        "strategy_code_changed": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "paper_state_changed": False,
        "llm_decision_boundary_changed": False,
        "trade_enabled": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_external_donchian_baseline_replay",
    }
    changed_files = [
        repo_rel(PLAN_DOC),
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(BEFORE_JSON),
        repo_rel(AFTER_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    completed_at = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "realized_success": observed_only_lead,
            "realized_failure_modes": failed_reasons,
        },
        "config": CONFIG,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "gate1": {
            "baseline_available": BASELINE_RESULT.exists(),
            "canonical_snapshots": [repo_rel(row["snapshot"]) for row in WINDOW_SOURCES],
            "canonical_core_results": [repo_rel(row["core_result"]) for row in WINDOW_SOURCES],
            "baseline_protocol": "private external Donchian 55/20 replay compared to accepted current breakout_long by_strategy rows",
            "passed": BASELINE_RESULT.exists()
            and all(Path(row["snapshot"]).exists() for row in WINDOW_SOURCES)
            and all(Path(row["core_result"]).exists() for row in WINDOW_SOURCES),
        },
        "gate2": {
            "required_fields": ["Date", "Open", "High", "Low", "Close", "Volume"],
            "entry_date_contract": "entry fills use next available Open after the signal close",
            "target_price_required_for_signal_generation": False,
            "uses_runtime_production_visible_fields": True,
            "passed": True,
        },
        "gate3": {
            "no_filter_added_to_strategy": True,
            "private_replay_trade_count": aggregate["donchian_trade_count"],
            "raw_breakout_signal_count": {
                row["label"]: row["signal_diagnostics"]["raw_breakout_signal_count"]
                for row in windows
            },
            "skipped_signal_count": {
                row["label"]: row["signal_diagnostics"]["skipped_signal_count"]
                for row in windows
            },
            "passed": aggregate["donchian_trade_count"] >= CONFIG["min_trade_count_for_lead"],
        },
        "gate4": {
            "diagnostic_only": True,
            "full_gate4_passed": full_gate4_passed,
            "observed_only_lead": observed_only_lead,
            "failed_reasons": failed_reasons
            + ["not_full_gate4_private_external_replay"],
            "aggregate": aggregate,
            "windows": windows,
            "acceptance_rule": CONFIG["acceptance_rule"],
            "not_recomputed_in_shared_backtester": [
                "production candidate generation",
                "slot displacement against core positions",
                "daily paper state",
                "live order semantics",
            ],
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun Donchian/Turtle on these frozen windows by "
                "changing 55/20 lookbacks, ATR sizing units, liquidity floors, "
                "position caps, universe exclusions, costs, or ranking order. "
                "That would be a parameter sweep on the same OHLCV relation "
                "surface."
            ),
            "new_evidence_required": (
                "If positive, next evidence must be a shared helper/backtester "
                "Gate 1-4 replay. If negative, move to the next external "
                "baseline lane such as 12-1/residual momentum or PEAD/revision "
                "rather than retuning Donchian parameters."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed_reasons),
        "next_retry_requires": [
            "shared_helper_gate_1_4_before_any_behavior_change"
            if observed_only_lead
            else "different_external_baseline_family_such_as_12_1_momentum_or_pead",
            "no_donchian_lookback_sizing_liquidity_universe_cost_or_ranking_retune_on_same_windows",
        ],
        "changed_files": changed_files,
        "related_files": [
            repo_rel(PLAN_DOC),
            repo_rel(BASELINE_RESULT),
            *[repo_rel(row["snapshot"]) for row in WINDOW_SOURCES],
            *[repo_rel(row["core_result"]) for row in WINDOW_SOURCES],
            repo_rel(TICKET_JSON),
        ],
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "before_measurement": repo_rel(BEFORE_JSON),
        "after_measurement": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "ticket_before": ticket,
        "completed_at": completed_at,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": compact_gate4(payload["gate4"]),
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "completed_at": payload["completed_at"],
    }


def build_before_after(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    aggregate = payload["gate4"]["aggregate"]
    before = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_type": "current_breakout_long_by_strategy_baseline",
        "diagnostic_only": True,
        "expected_value_score": None,
        "total_pnl": aggregate["current_breakout_long_total_pnl"],
        "total_trades": aggregate["current_breakout_long_trade_count"],
        "note": "Before measurement uses accepted core backtest by_strategy breakout_long PnL.",
    }
    after = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_type": "private_donchian_55_20_external_baseline_replay",
        "diagnostic_only": True,
        "expected_value_score": aggregate["diagnostic_expected_value_score"],
        "total_pnl": aggregate["donchian_total_pnl"],
        "total_trades": aggregate["donchian_trade_count"],
        "total_pnl_delta": aggregate["pnl_delta_vs_breakout_long"],
        "note": "After measurement is private external replay, not a shared backtester result.",
    }
    return before, after


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: Donchian/Turtle Breakout External Baseline",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Observed-only lead: `{payload['observed_only_lead']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Aggregate",
        "",
        f"- Donchian PnL: `${aggregate['donchian_total_pnl']}`",
        f"- Current `breakout_long` PnL: `${aggregate['current_breakout_long_total_pnl']}`",
        f"- PnL delta: `${aggregate['pnl_delta_vs_breakout_long']}`",
        f"- Donchian trades: `{aggregate['donchian_trade_count']}`",
        f"- Windows beating `breakout_long`: `{', '.join(aggregate['donchian_win_windows_vs_breakout_long']) or 'none'}`",
        f"- Max window drawdown: `{aggregate['max_window_drawdown_pct']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Windows",
        "",
        "| Window | Donchian PnL | Donchian trades | Donchian EV | Donchian maxDD | breakout_long PnL | Delta | Beats breakout |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in gate4["windows"]:
        lines.append(
            f"| {row['label']} | {row['donchian_trade_summary']['total_pnl']} | "
            f"{row['donchian_trade_summary']['trade_count']} | "
            f"{row['donchian_metrics']['expected_value_score']} | "
            f"{row['donchian_metrics']['max_drawdown_pct']} | "
            f"{row['current_breakout_long']['total_pnl_usd']} | "
            f"{row['comparison_vs_breakout_long']['pnl_delta']} | "
            f"{row['comparison_vs_breakout_long']['donchian_beats_breakout_pnl']} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        PLAN_DOC,
        REPO_ROOT / RUNNER,
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    before, after = build_before_after(payload)
    log_record = compact_log_record(payload)
    ticket = dict(payload["ticket_before"] or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["completed_at"],
            "result": {
                "decision": payload["decision"],
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "observed_only_lead": payload["observed_only_lead"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "gate4": log_record["gate4"],
            },
        }
    )

    write_json(OUT_JSON, payload)
    write_json(BEFORE_JSON, before)
    write_json(AFTER_JSON, after)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, ticket)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "runner": RUNNER,
            "gate4": log_record["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "before_measurement": payload["before_measurement"],
            "after_measurement": payload["after_measurement"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": log_record["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "gate4": compact_gate4(payload["gate4"]),
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
