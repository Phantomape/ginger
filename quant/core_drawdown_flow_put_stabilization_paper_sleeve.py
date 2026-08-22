"""Shared default-off observer for the deep-drawdown/flow/Put/stabilization rule.

The selector in this module is deliberately the single source of truth for
both historical replay and the daily paper ledger.  A signal is admitted only
after the signal-day close when all of the following are true:

* 60-session drawdown <= -15%;
* Wilder RSI14 <= 40 or 20-session return <= -15%;
* Moomoo DAY ``main_in_flow`` is positive;
* the quality-approved forward option snapshot has exactly two captured
  expiries and at least ten liquid rows for the ticker;
* the close is above the prior close and in the upper 45% of the daily range.

Complete candidates rank by the geometric mean of their same-day percentile
ranks for ``main_in_flow / prior ADV20`` and near-price Put-OI share.  The
default-off paper sleeve chooses top one while its single slot is empty,
enters at the following session open, and exits after ten sessions.  It never
emits or alters live orders.

User-authorized Moomoo research contract (2026-07-22): a DAY flow row dated D
is treated as stable and immutable, known after D's close, and usable for a
D+1 session paper entry.  ``fetched_at`` remains visible for audit but does not
veto a historical row under this explicit assumption.  Options keep their
stricter forward-collected ``usable_trade_date`` contract and fail closed.
"""

from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


_QUANT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QUANT_DIR.parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

try:
    from candidate_decision_training_ledger import next_session_after
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import atomic_write_text
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from moomoo_capital_flow_paper_sleeve import (
        EXCLUDED_TICKERS,
        flow_rows_by_ticker,
        load_moomoo_capital_flow_rows,
    )
    from us_market_calendar import is_us_equity_session
    from volume_breadth_breakout_paper_sleeve import (
        _date10,
        _float_or_none,
        _index_on_date,
        _normalise_ohlcv_rows,
        _safe,
    )
except ImportError:  # pragma: no cover - package-style test imports
    from quant.candidate_decision_training_ledger import next_session_after
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import atomic_write_text
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.moomoo_capital_flow_paper_sleeve import (
        EXCLUDED_TICKERS,
        flow_rows_by_ticker,
        load_moomoo_capital_flow_rows,
    )
    from quant.us_market_calendar import is_us_equity_session
    from quant.volume_breadth_breakout_paper_sleeve import (
        _date10,
        _float_or_none,
        _index_on_date,
        _normalise_ohlcv_rows,
        _safe,
    )


SLEEVE_NAME = "CORE_DRAWDOWN_FLOW_PUT_STABILIZATION_PAPER"
RULE_VERSION = "core_drawdown_flow_put_stabilization_top1_v1"
STATE_SCHEMA_VERSION = 1
FLOW_PIT_CONTRACT_VERSION = "owner_authorized_moomoo_day_stable_pit_d_plus_1_v1"
OPTIONS_PIT_CONTRACT_VERSION = "onclickmedia_forward_quote_date_next_session_v1"
NON_COMMON_STOCK_EXCLUSIONS = frozenset(set(EXCLUDED_TICKERS) | {"MUU", "SNXX"})

DEFAULT_OPTIONS_DIR = _REPO_ROOT / "data" / "non_ohlcv"
DEFAULT_OPTIONS_QUALITY_PATH = (
    DEFAULT_OPTIONS_DIR / "options_forward" / "options_collection_quality_gate.json"
)
DEFAULT_STATE_PATH = (
    _REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "core_drawdown_flow_put_stabilization"
    / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = DEFAULT_STATE_PATH.with_name("snapshots.jsonl")

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "drawdown_days": 60,
    "max_drawdown_60": -0.15,
    "rsi_days": 14,
    "max_rsi14": 40.0,
    "return_days": 20,
    "max_ret20": -0.15,
    "dollar_volume_days": 20,
    "min_main_in_flow": 0.0,
    "min_close_location": 0.55,
    "near_put_strike_low": 0.94,
    "put_denominator_strike_low": 0.75,
    "put_strike_high": 1.01,
    "required_option_expiries": 2,
    "min_liquid_option_rows": 10,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 1,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "atr_days": 14,
    "atr_target_mult": 3.5,
    "forward_gate_min_closed_trades": 20,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _inc(counter: dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + int(amount)


def _rows_by_ticker(ohlcv_by_ticker: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    return {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
        if rows is not None
    }


def _rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(avg_loss.ne(0.0), 100.0)
    rsi = rsi.where(avg_gain.ne(0.0) | avg_loss.ne(0.0), 50.0)
    return rsi


def _price_features(
    rows: list[dict[str, Any]], idx: int, config: dict[str, Any]
) -> dict[str, float] | None:
    drawdown_days = int(config["drawdown_days"])
    return_days = int(config["return_days"])
    dollar_volume_days = int(config["dollar_volume_days"])
    atr_days = int(config["atr_days"])
    minimum = max(drawdown_days - 1, return_days, dollar_volume_days, atr_days)
    if idx < minimum:
        return None

    window = rows[: idx + 1]
    close = pd.Series([_float_or_none(row.get("close")) for row in window], dtype=float)
    high = pd.Series([_float_or_none(row.get("high")) for row in window], dtype=float)
    low = pd.Series([_float_or_none(row.get("low")) for row in window], dtype=float)
    volume = pd.Series([_float_or_none(row.get("volume")) for row in window], dtype=float)
    if close.iloc[-1] <= 0 or close.iloc[-2] <= 0:
        return None

    rsi14 = _float_or_none(_rsi_wilder(close, int(config["rsi_days"])).iloc[-1])
    ret20 = _float_or_none(close.iloc[-1] / close.iloc[-1 - return_days] - 1.0)
    rolling_high = _float_or_none(close.iloc[-drawdown_days:].max())
    if rsi14 is None or ret20 is None or rolling_high is None or rolling_high <= 0:
        return None
    dd60 = float(close.iloc[-1] / rolling_high - 1.0)

    prior_dollar_volume = close.shift(1) * volume.shift(1)
    adv20 = _float_or_none(prior_dollar_volume.iloc[-dollar_volume_days:].mean())
    if adv20 is None or adv20 <= 0:
        return None

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = _float_or_none(true_range.rolling(atr_days, min_periods=atr_days).mean().iloc[-1])
    if atr14 is None or atr14 <= 0:
        return None

    day_high = _float_or_none(high.iloc[-1])
    day_low = _float_or_none(low.iloc[-1])
    if day_high is None or day_low is None or day_high <= day_low:
        return None
    close_location = float((close.iloc[-1] - day_low) / (day_high - day_low))
    return {
        "close": float(close.iloc[-1]),
        "previous_close": float(close.iloc[-2]),
        "rsi14": float(rsi14),
        "ret20": float(ret20),
        "dd60": dd60,
        "prior_adv20_usd": float(adv20),
        "close_location": close_location,
        "atr14": float(atr14),
    }


def _average_pct_ranks(values: list[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and math.isclose(
            values[order[end]], values[order[cursor]], rel_tol=0.0, abs_tol=1e-15
        ):
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = average_rank / len(values)
        cursor = end
    return ranks


def load_options_quality(
    path: Path | str = DEFAULT_OPTIONS_QUALITY_PATH,
) -> dict[str, Any]:
    quality_path = Path(path)
    if not quality_path.exists():
        return {"status": "missing", "by_quote_date": {}}
    try:
        payload = json.loads(quality_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid", "by_quote_date": {}}
    return payload if isinstance(payload, dict) else {"status": "invalid", "by_quote_date": {}}


def load_option_chain_snapshot(
    as_of: str,
    *,
    options_dir: Path | str = DEFAULT_OPTIONS_DIR,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Load one exact quote-date snapshot; never substitute a nearby date."""
    quote_date = _date10(as_of)
    path = Path(options_dir) / f"options_onclickmedia_chain_{quote_date.replace('-', '')}.jsonl"
    if not path.exists():
        return {}, {"status": "missing_exact_quote_date_file", "path": str(path), "rows": 0}
    aggregates: dict[str, dict[str, Any]] = {}
    raw_rows = 0
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_rows += 1
                ticker = str(row.get("ticker") or "").upper().strip()
                row_date = _date10(row.get("quote_date") or row.get("date"))
                if not ticker or row_date != quote_date:
                    continue
                state = aggregates.setdefault(
                    ticker,
                    {
                        "captured_rows": 0,
                        "liquid_rows": 0,
                        "expiries": set(),
                        "put_rows": [],
                        "usable_trade_dates": set(),
                        "retrieved_ats": set(),
                        "pit_safe_rows": 0,
                    },
                )
                state["captured_rows"] += 1
                expiry = row.get("expiration") or row.get("expiry")
                if expiry:
                    state["expiries"].add(str(expiry))
                if row.get("option_liquidity_pass") is True:
                    state["liquid_rows"] += 1
                if row.get("pit_safe") is True:
                    state["pit_safe_rows"] += 1
                usable = _date10(row.get("usable_trade_date"))
                if usable:
                    state["usable_trade_dates"].add(usable)
                retrieved_at = str(row.get("retrieved_at") or "").strip()
                if retrieved_at:
                    state["retrieved_ats"].add(retrieved_at)
                if str(row.get("call_put") or "").lower() == "put":
                    strike = _float_or_none(row.get("strike"))
                    open_interest = _float_or_none(row.get("open_interest"))
                    if strike is not None and open_interest is not None:
                        state["put_rows"].append((float(strike), max(0.0, float(open_interest))))
    except OSError:
        return {}, {"status": "unreadable_exact_quote_date_file", "path": str(path), "rows": 0}
    return aggregates, {
        "status": "loaded",
        "path": str(path),
        "rows": raw_rows,
        "ticker_count": len(aggregates),
        "quote_date": quote_date,
    }


def build_core_drawdown_flow_put_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    flow_by_ticker: dict[str, dict[str, dict[str, Any]]],
    option_by_ticker: dict[str, dict[str, Any]],
    tickers: Iterable[str],
    as_of: str,
    options_scoring_allowed: bool,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Apply the frozen selector.  Historical and daily callers both use it."""
    cfg = _config(config)
    signal_date = _date10(as_of)
    rejects: dict[str, int] = {}
    stage_counts = {
        "universe": 0,
        "price_history_ready": 0,
        "deep_drawdown_distress": 0,
        "price_stabilized": 0,
        "flow_complete": 0,
        "options_complete": 0,
    }
    complete: list[dict[str, Any]] = []
    expected_entry_date = next_session_after(signal_date)

    for raw_ticker in sorted({str(item).upper() for item in tickers if item}):
        ticker = raw_ticker.strip()
        if not ticker or ticker in NON_COMMON_STOCK_EXCLUSIONS or ticker == "SPY":
            _inc(rejects, "excluded_non_common_stock")
            continue
        stage_counts["universe"] += 1
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, signal_date)
        if idx is None:
            _inc(rejects, "missing_price_row_asof")
            continue
        features = _price_features(rows, idx, cfg)
        if features is None:
            _inc(rejects, "insufficient_price_history")
            continue
        stage_counts["price_history_ready"] += 1
        if not (
            features["dd60"] <= float(cfg["max_drawdown_60"])
            and (
                features["rsi14"] <= float(cfg["max_rsi14"])
                or features["ret20"] <= float(cfg["max_ret20"])
            )
        ):
            _inc(rejects, "not_deep_drawdown_distress")
            continue
        stage_counts["deep_drawdown_distress"] += 1
        if not (
            features["close"] > features["previous_close"]
            and features["close_location"] >= float(cfg["min_close_location"])
        ):
            _inc(rejects, "price_not_stabilized")
            continue
        stage_counts["price_stabilized"] += 1

        flow = (flow_by_ticker.get(ticker) or {}).get(signal_date)
        main_in_flow = _float_or_none((flow or {}).get("main_in_flow"))
        if main_in_flow is None:
            _inc(rejects, "missing_flow_row_asof")
            continue
        if main_in_flow <= float(cfg["min_main_in_flow"]):
            _inc(rejects, "main_in_flow_not_positive")
            continue
        stage_counts["flow_complete"] += 1

        if not options_scoring_allowed:
            _inc(rejects, "options_quote_date_quarantined")
            continue
        chain = option_by_ticker.get(ticker)
        if not chain:
            _inc(rejects, "missing_options_row_asof")
            continue
        if int(chain.get("liquid_rows") or 0) < int(cfg["min_liquid_option_rows"]):
            _inc(rejects, "options_lt_10_liquid_rows")
            continue
        expiries = sorted(chain.get("expiries") or [])
        if len(expiries) != int(cfg["required_option_expiries"]):
            _inc(rejects, "options_not_exactly_two_expiries")
            continue
        usable_dates = sorted(chain.get("usable_trade_dates") or [])
        if len(usable_dates) != 1 or usable_dates[0] != expected_entry_date:
            _inc(rejects, "options_usable_trade_date_mismatch")
            continue
        if int(chain.get("pit_safe_rows") or 0) != int(chain.get("captured_rows") or 0):
            _inc(rejects, "options_not_all_pit_safe")
            continue
        put_rows = chain.get("put_rows") or []
        spot = features["close"]
        numerator = sum(
            oi
            for strike, oi in put_rows
            if float(cfg["near_put_strike_low"]) * spot
            <= strike
            <= float(cfg["put_strike_high"]) * spot
        )
        denominator = sum(
            oi
            for strike, oi in put_rows
            if float(cfg["put_denominator_strike_low"]) * spot
            <= strike
            <= float(cfg["put_strike_high"]) * spot
        )
        if denominator <= 0:
            _inc(rejects, "put_oi_denominator_nonpositive")
            continue
        stage_counts["options_complete"] += 1

        flow_strength = float(main_in_flow) / features["prior_adv20_usd"]
        put_share = float(numerator / denominator)
        complete.append(
            {
                "sleeve": SLEEVE_NAME,
                "strategy": "core_drawdown_flow_put_stabilization_candidate_pool",
                "rule_version": RULE_VERSION,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "entry_date": expected_entry_date,
                "target_price": round(
                    features["close"] + float(cfg["atr_target_mult"]) * features["atr14"],
                    4,
                ),
                "target_price_role": "signal_contract_diagnostic_fixed_h10_exit_remains_primary",
                "close": round(features["close"], 4),
                "previous_close": round(features["previous_close"], 4),
                "rsi14": round(features["rsi14"], 6),
                "ret20": round(features["ret20"], 8),
                "dd60": round(features["dd60"], 8),
                "close_location": round(features["close_location"], 8),
                "atr14": round(features["atr14"], 6),
                "prior_adv20_usd": round(features["prior_adv20_usd"], 2),
                "main_in_flow": round(float(main_in_flow), 2),
                "flow_strength": round(flow_strength, 10),
                "flow_fetched_at": (flow or {}).get("fetched_at"),
                "flow_pit_contract": FLOW_PIT_CONTRACT_VERSION,
                "near_put_oi_share_proxy": round(put_share, 10),
                "near_put_oi_numerator": round(float(numerator), 2),
                "near_put_oi_denominator": round(float(denominator), 2),
                "liquid_option_rows": int(chain.get("liquid_rows") or 0),
                "captured_option_rows": int(chain.get("captured_rows") or 0),
                "option_expiries": expiries,
                "option_usable_trade_date": usable_dates[0],
                "options_pit_contract": OPTIONS_PIT_CONTRACT_VERSION,
                "intended_notional": float(cfg["paper_notional_usd"]),
                "known_at": "after_signal_date_close_before_next_session_open",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    flow_ranks = _average_pct_ranks([row["flow_strength"] for row in complete])
    put_ranks = _average_pct_ranks([row["near_put_oi_share_proxy"] for row in complete])
    for row, flow_rank, put_rank in zip(complete, flow_ranks, put_ranks):
        row["flow_rank_pct"] = round(flow_rank, 10)
        row["put_rank_pct"] = round(put_rank, 10)
        row["score"] = round(math.sqrt(flow_rank * put_rank), 10)
    complete.sort(key=lambda row: (-row["score"], row["dd60"], row["ticker"]))
    for rank, row in enumerate(complete, 1):
        row["cross_sectional_rank"] = rank
    return complete, dict(sorted(rejects.items())), stage_counts


def _quality_for_date(quality: dict[str, Any], as_of: str) -> tuple[bool, dict[str, Any]]:
    state = (quality.get("by_quote_date") or {}).get(_date10(as_of))
    if not isinstance(state, dict):
        return False, {"status": "missing_quality_row", "scoring_allowed": False}
    return bool(state.get("scoring_allowed") is True), state


def _pnl(entry_price: float, exit_price: float, notional: float, cost: float) -> float:
    return notional * ((exit_price / entry_price) - 1.0 - cost)


def _net_return(entry_price: float, exit_price: float, cost: float) -> float:
    return (exit_price / entry_price) - 1.0 - cost


def _metrics(
    *,
    daily_equity: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    signals_generated: int,
    signals_survived: int,
    initial_capital: float,
) -> dict[str, Any]:
    equity = [float(row["equity"]) for row in daily_equity]
    returns: list[float] = []
    for previous, current in zip(equity, equity[1:]):
        returns.append(current / previous - 1.0 if previous else 0.0)
    sharpe = 0.0
    if len(returns) >= 2:
        std = float(np.std(returns, ddof=1))
        if std > 0:
            sharpe = float(np.mean(returns) / std * math.sqrt(252.0))
    max_drawdown = 0.0
    peak = initial_capital
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)
    ending = equity[-1] if equity else initial_capital
    total_pnl = ending - initial_capital
    total_return = total_pnl / initial_capital
    realized_pnl = sum(float(trade.get("pnl") or 0.0) for trade in trades)
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    survival = signals_survived / signals_generated if signals_generated else 0.0
    return {
        "expected_value_score": round(total_return * abs(sharpe), 8),
        "strategy_total_return_pct": round(total_return, 8),
        "total_pnl": round(total_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl_at_window_end": round(total_pnl - realized_pnl, 2),
        "sharpe_daily": round(sharpe, 8),
        "max_drawdown_pct": round(max_drawdown, 8),
        "win_rate": round(wins / len(trades), 8) if trades else None,
        "trade_count": len(trades),
        "signals_generated": int(signals_generated),
        "signals_survived": int(signals_survived),
        "survival_rate": round(survival, 8),
        "daily_return_count": len(returns),
    }


def replay_core_drawdown_flow_put_sleeve(
    *,
    ohlcv_by_ticker: dict[str, Any],
    flow_rows: list[dict[str, Any]],
    start: str,
    end: str,
    tickers: Iterable[str] | None = None,
    options_dir: Path | str = DEFAULT_OPTIONS_DIR,
    options_quality_path: Path | str = DEFAULT_OPTIONS_QUALITY_PATH,
    config: dict[str, Any] | None = None,
    initial_capital: float = 100_000.0,
) -> dict[str, Any]:
    """Chronological one-slot replay using the same selector as daily wiring."""
    cfg = _config(config)
    rows_by_ticker = _rows_by_ticker(ohlcv_by_ticker)
    spy_rows = rows_by_ticker.get("SPY") or []
    sessions = [
        str(row.get("date"))
        for row in spy_rows
        if start <= str(row.get("date")) <= end
    ]
    universe = sorted(
        {str(t).upper() for t in (tickers or rows_by_ticker) if t}
        - set(NON_COMMON_STOCK_EXCLUSIONS)
        - {"SPY"}
    )
    flow_index = flow_rows_by_ticker(flow_rows)
    quality = load_options_quality(options_quality_path)
    option_cache: dict[str, tuple[dict[str, dict[str, Any]], dict[str, Any]]] = {}
    coverage = {
        "price_session_count": len(sessions),
        "flow_dates_in_window": set(),
        "option_files_in_window": [],
        "quality_allowed_dates": [],
        "quality_blocked_dates": [],
        "stage_counts": {
            "universe": 0,
            "price_history_ready": 0,
            "deep_drawdown_distress": 0,
            "price_stabilized": 0,
            "flow_complete": 0,
            "options_complete": 0,
        },
        "reject_totals": {},
    }
    for by_date in flow_index.values():
        coverage["flow_dates_in_window"].update(
            day for day in by_date if start <= day <= end
        )

    pending: dict[str, Any] | None = None
    active: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    daily_equity: list[dict[str, Any]] = []
    realized_pnl = 0.0
    signals_generated = 0
    signals_survived = 0
    selected_decisions = 0

    for session in sessions:
        if pending is not None:
            ticker_rows = rows_by_ticker.get(pending["ticker"]) or []
            idx = _index_on_date(ticker_rows, session)
            if session == pending["entry_date"] and idx is not None:
                open_price = _float_or_none(ticker_rows[idx].get("open"))
                if open_price is not None and open_price > 0:
                    active = {
                        **pending,
                        "entry_price": apply_entry_fill(open_price),
                        "entry_date": session,
                        "entry_idx": idx,
                    }
                pending = None
            elif session > pending["entry_date"]:
                pending = None

        if active is not None:
            ticker_rows = rows_by_ticker.get(active["ticker"]) or []
            idx = _index_on_date(ticker_rows, session)
            if idx is not None and idx >= int(active["entry_idx"]) + int(cfg["hold_days"]):
                close_price = _float_or_none(ticker_rows[idx].get("close"))
                if close_price is not None and close_price > 0:
                    exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
                    pnl = _pnl(
                        active["entry_price"],
                        exit_price,
                        float(cfg["paper_notional_usd"]),
                        float(cfg["round_trip_cost_pct"]),
                    )
                    trade = {
                        key: deepcopy(active[key])
                        for key in (
                            "ticker",
                            "signal_date",
                            "entry_date",
                            "target_price",
                            "score",
                            "flow_strength",
                            "near_put_oi_share_proxy",
                            "dd60",
                            "rsi14",
                            "ret20",
                            "close_location",
                        )
                    }
                    trade.update(
                        {
                            "exit_date": session,
                            "entry_price": round(float(active["entry_price"]), 4),
                            "exit_price": round(float(exit_price), 4),
                            "hold_days": int(cfg["hold_days"]),
                            "paper_notional_usd": float(cfg["paper_notional_usd"]),
                            "pnl": round(float(pnl), 2),
                            "pnl_pct_net": round(
                                _net_return(
                                    active["entry_price"],
                                    exit_price,
                                    float(cfg["round_trip_cost_pct"]),
                                ),
                                8,
                            ),
                            "trade_enabled": False,
                        }
                    )
                    trades.append(trade)
                    realized_pnl += pnl
                    active = None

        # Evaluate every session so coverage and Gate 3 describe the signal,
        # independently of whether the one-slot paper portfolio is occupied.
        option_state, option_meta = option_cache.setdefault(
            session, load_option_chain_snapshot(session, options_dir=options_dir)
        )
        scoring_allowed, _quality_state = _quality_for_date(quality, session)
        if option_meta.get("status") == "loaded":
            coverage["option_files_in_window"].append(session)
        if scoring_allowed:
            coverage["quality_allowed_dates"].append(session)
        else:
            coverage["quality_blocked_dates"].append(session)
        candidates, rejects, stage_counts = build_core_drawdown_flow_put_candidates(
            rows_by_ticker=rows_by_ticker,
            flow_by_ticker=flow_index,
            option_by_ticker=option_state,
            tickers=universe,
            as_of=session,
            options_scoring_allowed=scoring_allowed,
            config=cfg,
        )
        signals_generated += stage_counts["price_stabilized"]
        signals_survived += stage_counts["options_complete"]
        for key, value in stage_counts.items():
            coverage["stage_counts"][key] += value
        for key, value in rejects.items():
            _inc(coverage["reject_totals"], key, value)
        if pending is None and active is None and candidates:
            pending = deepcopy(candidates[0])
            selected_decisions += 1

        mark_to_market = 0.0
        if active is not None:
            ticker_rows = rows_by_ticker.get(active["ticker"]) or []
            idx = _index_on_date(ticker_rows, session)
            if idx is not None:
                close_price = _float_or_none(ticker_rows[idx].get("close"))
                if close_price is not None and close_price > 0:
                    exit_mark = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
                    mark_to_market = _pnl(
                        active["entry_price"],
                        exit_mark,
                        float(cfg["paper_notional_usd"]),
                        float(cfg["round_trip_cost_pct"]),
                    )
        daily_equity.append(
            {
                "date": session,
                "equity": round(initial_capital + realized_pnl + mark_to_market, 6),
            }
        )

    metrics = _metrics(
        daily_equity=daily_equity,
        trades=trades,
        signals_generated=signals_generated,
        signals_survived=signals_survived,
        initial_capital=initial_capital,
    )
    metrics["selected_decisions"] = selected_decisions
    metrics["unsettled_position_count"] = int(active is not None) + int(pending is not None)
    flow_dates = sorted(coverage["flow_dates_in_window"])
    coverage["flow_dates_in_window"] = len(flow_dates)
    coverage["first_flow_date"] = flow_dates[0] if flow_dates else None
    coverage["last_flow_date"] = flow_dates[-1] if flow_dates else None
    coverage["option_files_in_window"] = sorted(set(coverage["option_files_in_window"]))
    coverage["quality_allowed_dates"] = sorted(set(coverage["quality_allowed_dates"]))
    coverage["quality_blocked_dates"] = sorted(set(coverage["quality_blocked_dates"]))
    coverage["reject_totals"] = dict(sorted(coverage["reject_totals"].items()))
    evidence_status = "evaluable" if coverage["option_files_in_window"] else "blocked_no_options_history"
    gate3_passed = metrics["signals_generated"] > 0 and metrics["survival_rate"] >= 0.05
    touch_density_passed = selected_decisions >= 5 and metrics["trade_count"] >= 5
    return {
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "start": start,
        "end": end,
        "evidence_status": evidence_status,
        "metrics": metrics,
        "coverage": coverage,
        "trades": trades,
        "daily_equity": daily_equity,
        "gate_checks": {
            "gate2_entry_date_present": all(bool(row.get("entry_date")) for row in trades),
            "gate2_target_price_present": all(row.get("target_price") is not None for row in trades),
            "gate3_survival_at_least_5pct": gate3_passed,
            "gate_preflight_at_least_5_selected_and_settled": touch_density_passed,
            "gate4_eligible": (
                evidence_status == "evaluable" and gate3_passed and touch_density_passed
            ),
        },
        "trade_enabled": False,
    }


def empty_core_drawdown_flow_put_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": 0,
        "new_pending_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "forward_paper_gate": {
            "passed": False,
            "status": "blocked",
            "reasons": [reason],
            "trade_enabled_after_gate": False,
        },
        "production_impact": _production_impact(),
        "error": reason,
    }


def empty_core_drawdown_flow_put_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_core_drawdown_flow_put_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_core_drawdown_flow_put_state()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return empty_core_drawdown_flow_put_state()
    state = empty_core_drawdown_flow_put_state()
    if isinstance(payload, dict):
        state.update(payload)
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_entries"):
        if not isinstance(state.get(key), list):
            state[key] = []
    return state


def _save_state(state: dict[str, Any], path: Path | str) -> None:
    state["updated_at"] = utc_now_iso()
    atomic_write_text(json.dumps(_safe(state), indent=2, sort_keys=True) + "\n", Path(path))


def _append_snapshot(snapshot: dict[str, Any], path: Path | str) -> None:
    snapshot_path = Path(path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def _advance_state(
    state: dict[str, Any],
    *,
    as_of: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    still_pending: list[dict[str, Any]] = []
    for entry in state.get("pending_entries") or []:
        expected = str(entry.get("entry_date") or "")
        ticker = str(entry.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if as_of < expected:
            still_pending.append(entry)
            continue
        open_price = _float_or_none(rows[idx].get("open")) if idx is not None else None
        if as_of != expected or open_price is None or open_price <= 0:
            missed = deepcopy(entry)
            missed.update({"status": "skipped_missing_exact_next_open", "skipped_asof": as_of})
            skipped.append(missed)
            state["skipped_entries"].append(missed)
            continue
        position = deepcopy(entry)
        position.update(
            {
                "status": "open",
                "entry_price": apply_entry_fill(open_price),
                "entry_index": idx,
                "observed_trading_days": 0,
            }
        )
        state["open_positions"].append(position)
        filled.append(position)
    state["pending_entries"] = still_pending

    closed_today: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None:
            still_open.append(position)
            continue
        close_price = _float_or_none(rows[idx].get("close"))
        if close_price is None or close_price <= 0:
            still_open.append(position)
            continue
        entry_index = position.get("entry_index")
        entry_index = int(entry_index) if entry_index is not None else int(idx)
        trading_days = max(0, int(idx) - entry_index)
        position["observed_trading_days"] = trading_days
        exit_mark = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
        position["last_price"] = close_price
        position["last_price_asof"] = as_of
        position["unrealized_pnl"] = _pnl(
            float(position["entry_price"]),
            exit_mark,
            float(position["notional"]),
            float(config["round_trip_cost_pct"]),
        )
        if trading_days >= int(config["hold_days"]):
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_mark,
                    "exit_reason": "fixed_h10_close",
                    "pnl": position["unrealized_pnl"],
                    "return_pct_net": _net_return(
                        float(position["entry_price"]),
                        exit_mark,
                        float(config["round_trip_cost_pct"]),
                    ),
                }
            )
            state["closed_positions"].append(closed)
            closed_today.append(closed)
        else:
            still_open.append(position)
    state["open_positions"] = still_open
    return filled, skipped, closed_today


def build_core_drawdown_flow_put_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    flow_rows: list[dict[str, Any]] | None = None,
    candidate_universe: Iterable[str] | None = None,
    state: dict[str, Any] | None = None,
    options_dir: Path | str = DEFAULT_OPTIONS_DIR,
    options_quality_path: Path | str = DEFAULT_OPTIONS_QUALITY_PATH,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    if not is_us_equity_session(as_of_date):
        return empty_core_drawdown_flow_put_snapshot(as_of_date, "non_us_equity_session")
    rows_by_ticker = _rows_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_core_drawdown_flow_put_snapshot(as_of_date, "missing_ohlcv")
    universe = sorted(
        {str(t).upper() for t in (candidate_universe or rows_by_ticker) if t}
        - set(NON_COMMON_STOCK_EXCLUSIONS)
        - {"SPY"}
    )
    flow_rows = flow_rows if flow_rows is not None else load_moomoo_capital_flow_rows()
    flow_index = flow_rows_by_ticker(flow_rows or [])
    options, options_meta = load_option_chain_snapshot(as_of_date, options_dir=options_dir)
    quality = load_options_quality(options_quality_path)
    scoring_allowed, quality_state = _quality_for_date(quality, as_of_date)

    working_state = deepcopy(state if state is not None else load_core_drawdown_flow_put_state(state_path))
    filled, skipped, closed_today = _advance_state(
        working_state, as_of=as_of_date, rows_by_ticker=rows_by_ticker, config=cfg
    )
    candidates, rejects, stage_counts = build_core_drawdown_flow_put_candidates(
        rows_by_ticker=rows_by_ticker,
        flow_by_ticker=flow_index,
        option_by_ticker=options,
        tickers=universe,
        as_of=as_of_date,
        options_scoring_allowed=scoring_allowed,
        config=cfg,
    )
    pending_today = sum(
        1
        for row in working_state.get("pending_entries") or []
        if row.get("signal_date") == as_of_date
    )
    room = max(
        0,
        int(cfg["max_active_positions"])
        - len(working_state.get("pending_entries") or [])
        - len(working_state.get("open_positions") or []),
    )
    slots = max(0, int(cfg["daily_entry_slots"]) - pending_today)
    new_pending: list[dict[str, Any]] = []
    if room > 0 and slots > 0 and candidates:
        candidate = deepcopy(candidates[0])
        decision_id = f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of_date}:{candidate['ticker']}"
        existing_ids = {
            str(row.get("decision_id") or "")
            for key in ("pending_entries", "open_positions", "closed_positions", "skipped_entries")
            for row in working_state.get(key) or []
        }
        if decision_id not in existing_ids:
            entry = {
                **candidate,
                "decision_id": decision_id,
                "status": "pending_next_open",
                "created_asof": as_of_date,
                "notional": float(cfg["paper_notional_usd"]),
            }
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)

    closed = working_state.get("closed_positions") or []
    realized = sum(float(row.get("pnl") or 0.0) for row in closed)
    wins = sum(1 for row in closed if float(row.get("pnl") or 0.0) > 0)
    gate_reasons = []
    if len(closed) < int(cfg["forward_gate_min_closed_trades"]):
        gate_reasons.append("min_closed_trades")
    if realized <= 0:
        gate_reasons.append("positive_net_pnl")
    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": min(len(candidates), int(cfg["daily_entry_slots"])),
        "raw_candidate_count": len(candidates),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled),
        "skipped_count_today": len(skipped),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(working_state.get("open_positions") or []),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(realized, 2),
        "win_rate_to_date": round(wins / len(closed), 8) if closed else None,
        "data_source": {
            "flow_row_count": len(flow_rows or []),
            "flow_pit_contract": FLOW_PIT_CONTRACT_VERSION,
            "options": options_meta,
            "options_quality_status": quality_state.get("status"),
            "options_scoring_allowed": scoring_allowed,
            "options_pit_contract": OPTIONS_PIT_CONTRACT_VERSION,
        },
        "stage_counts": stage_counts,
        "candidate_reject_counts": rejects,
        "candidates": _safe(candidates[: int(cfg["daily_entry_slots"])]),
        "new_pending_entries": _safe(new_pending),
        "filled_entries_today": _safe(filled),
        "skipped_entries_today": _safe(skipped),
        "closed_positions_today": _safe(closed_today),
        "pending_entries": _safe(working_state.get("pending_entries") or []),
        "open_positions": _safe(working_state.get("open_positions") or []),
        "forward_paper_gate": {
            "passed": not gate_reasons,
            "status": "passed" if not gate_reasons else "blocked",
            "reasons": gate_reasons,
            "metrics": {"closed_trades": len(closed), "realized_pnl": round(realized, 2)},
            "trade_enabled_after_gate": False,
        },
        "production_impact": _production_impact(),
    }
    if persist:
        _save_state(working_state, state_path)
        _append_snapshot(snapshot, snapshot_log_path)
    return snapshot


def prep_and_build_core_drawdown_flow_put_snapshot(
    *,
    as_of: str,
    ohlcv_dict: dict[str, Any],
    spy_ohlcv: Any = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # open_prices/current_prices are accepted for the standard run.py adapter
    # shape.  Exact historical bars remain authoritative for this EOD observer.
    del open_prices, current_prices
    ohlcv = dict(ohlcv_dict or {})
    if spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_core_drawdown_flow_put_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=ohlcv.keys(),
    )


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "live_ready": False,
        "parity_rule": "shared_core_drawdown_flow_put_stabilization_selector_v1",
    }


__all__ = [
    "FLOW_PIT_CONTRACT_VERSION",
    "OPTIONS_PIT_CONTRACT_VERSION",
    "NON_COMMON_STOCK_EXCLUSIONS",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "build_core_drawdown_flow_put_candidates",
    "build_core_drawdown_flow_put_snapshot",
    "empty_core_drawdown_flow_put_snapshot",
    "load_option_chain_snapshot",
    "prep_and_build_core_drawdown_flow_put_snapshot",
    "replay_core_drawdown_flow_put_sleeve",
]
