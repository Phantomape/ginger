"""
BTC/USD crypto sleeve advice for the daily production report.

This module is intentionally isolated from the stock signal engine.  It gives
one spot-only BTC target allocation for a small experimental sleeve, using a
daily trend switch that was chosen because moomoo's crypto fee makes frequent
hourly/4h trading unattractive.
"""

import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from data_paths import data_artifact_path
from yfinance_bootstrap import (
    configure_yfinance_runtime,
    download_with_rate_limit_retry,
)

logger = logging.getLogger(__name__)


DEFAULT_CRYPTO_CONFIG = {
    "enabled": True,
    "symbol": "BTC-USD",
    "display_symbol": "BTC/USD",
    "broker": "moomoo",
    "sleeve_value_usd": 8000.0,
    "current_position_pct": None,
    "fee_pct_per_side": 0.0049,
    "policy": "daily_ema20_ema100_spot_trend",
    "min_rebalance_delta_pct": 0.10,
}


def load_crypto_config(path=None):
    """Load optional crypto sleeve settings from data/state/crypto/crypto_positions.json."""
    if path is None:
        path = data_artifact_path("crypto_positions")

    config = dict(DEFAULT_CRYPTO_CONFIG)
    if not os.path.exists(path):
        config["config_path"] = path
        config["config_loaded"] = False
        return config

    with open(path, "r", encoding="utf-8") as f:
        user_config = json.load(f)
    config.update(user_config or {})
    config["config_path"] = path
    config["config_loaded"] = True
    return config


def fetch_crypto_ohlcv(symbol="BTC-USD", lookback_days=900):
    """Fetch daily crypto OHLCV and normalize column names."""
    configure_yfinance_runtime()
    end = datetime.now(timezone.utc)
    start = end - pd.Timedelta(days=lookback_days)
    data = download_with_rate_limit_retry(
        symbol,
        start=start.date().isoformat(),
        end=(end + pd.Timedelta(days=1)).date().isoformat(),
        interval="1d",
        progress=False,
        auto_adjust=False,
        retry_logger=logger,
    )
    return normalize_crypto_ohlcv(data, symbol=symbol)


def normalize_crypto_ohlcv(data, symbol="BTC-USD"):
    """Return lower-case OHLCV columns from yfinance output."""
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.copy()
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(symbol, level=1, axis=1)
        except Exception:
            df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={c: str(c).lower().replace(" ", "_") for c in df.columns})
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{symbol}: missing OHLCV columns {missing}")
    df = df[required].dropna().copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df


def completed_daily_bars(df, now=None):
    """
    Keep only completed UTC daily candles.

    BTC trades 24/7.  A daily yfinance row with today's UTC date can be a
    partial candle during the US afternoon, so production advice should ignore
    it until the UTC day has closed.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today_utc = pd.Timestamp(now).tz_convert("UTC").date()
    out = df.copy()
    out = out[[idx.date() < today_utc for idx in out.index]]
    return out


def compute_crypto_indicators(df):
    """Attach the indicators used by the BTC sleeve policy."""
    out = df.copy()
    close = out["close"]
    out["ema20"] = close.ewm(span=20, adjust=False).mean()
    out["ema100"] = close.ewm(span=100, adjust=False).mean()
    out["sma200"] = close.rolling(200).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["rsi14"] = 100 - (100 / (1 + rs))
    out["ret7d"] = close.pct_change(7)
    return out


def _round_float(value, digits=4):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def build_crypto_snapshot(df, now=None):
    """Build the latest completed daily BTC snapshot for decision logic."""
    completed = completed_daily_bars(df, now=now)
    with_indicators = compute_crypto_indicators(completed)
    ready = with_indicators.dropna(subset=["ema20", "ema100", "sma200"])
    if ready.empty:
        return None
    row = ready.iloc[-1]
    return {
        "asof_date": ready.index[-1].date().isoformat(),
        "close": _round_float(row.get("close"), 2),
        "ema20": _round_float(row.get("ema20"), 2),
        "ema100": _round_float(row.get("ema100"), 2),
        "sma200": _round_float(row.get("sma200"), 2),
        "rsi14": _round_float(row.get("rsi14"), 2),
        "ret7d_pct": _round_float((row.get("ret7d") or 0) * 100, 2),
    }


def decide_crypto_target(snapshot):
    """
    Decide target BTC sleeve exposure from completed daily indicators.

    - Full risk: EMA20 > EMA100, close > EMA100, and close > SMA200.
    - Partial risk: EMA20 > EMA100 and close > EMA100, but still below SMA200.
    - Cash: trend switch is off.
    """
    close = snapshot["close"]
    ema20 = snapshot["ema20"]
    ema100 = snapshot["ema100"]
    sma200 = snapshot["sma200"]
    trend_on = ema20 > ema100 and close > ema100
    above_sma200 = close > sma200

    if trend_on and above_sma200:
        return {
            "state": "RISK_ON_FULL",
            "target_position_pct": 1.0,
            "reason": "BTC daily trend is on and price is above the 200-day average.",
        }
    if trend_on:
        return {
            "state": "RISK_ON_PARTIAL",
            "target_position_pct": 0.70,
            "reason": "BTC daily trend is on, but price remains below the 200-day average.",
        }
    return {
        "state": "RISK_OFF",
        "target_position_pct": 0.0,
        "reason": "BTC daily trend switch is off.",
    }


def build_rebalance_action(target_pct, config):
    """Convert target exposure into a human-actionable rebalance note."""
    current_pct = config.get("current_position_pct")
    sleeve_value = float(config.get("sleeve_value_usd") or 0)
    min_delta = float(config.get("min_rebalance_delta_pct") or 0.0)

    if current_pct is None:
        return {
            "action": "SET_TARGET",
            "current_position_pct": None,
            "target_position_pct": target_pct,
            "trade_value_usd": None,
            "note": "Current BTC sleeve exposure is not configured; compare manually.",
        }

    current_pct = float(current_pct)
    delta_pct = target_pct - current_pct
    trade_value = sleeve_value * delta_pct
    if abs(delta_pct) < min_delta:
        action = "HOLD"
    elif delta_pct > 0:
        action = "BUY"
    else:
        action = "SELL"

    return {
        "action": action,
        "current_position_pct": round(current_pct, 4),
        "target_position_pct": round(target_pct, 4),
        "delta_position_pct": round(delta_pct, 4),
        "trade_value_usd": round(trade_value, 2),
        "note": (
            f"Rebalance only when target-current exposure differs by "
            f"{min_delta * 100:.0f}% or more."
        ),
    }


def empty_crypto_sleeve_advice(error):
    """Return a non-fatal crypto sleeve payload when data is unavailable."""
    return {
        "enabled": False,
        "asset_class": "crypto",
        "symbol": DEFAULT_CRYPTO_CONFIG["symbol"],
        "error": str(error),
        "production_impact": {
            "alters_stock_orders": False,
            "alters_crypto_orders": False,
        },
    }


def build_crypto_sleeve_advice(config=None, ohlcv=None, now=None):
    """Build production BTC/USD advice without touching stock strategy state."""
    config = dict(DEFAULT_CRYPTO_CONFIG if config is None else config)
    if not config.get("enabled", True):
        return {
            "enabled": False,
            "asset_class": "crypto",
            "symbol": config.get("symbol", "BTC-USD"),
            "reason": "Crypto sleeve disabled in config.",
            "production_impact": {
                "alters_stock_orders": False,
                "alters_crypto_orders": False,
            },
        }

    symbol = config.get("symbol", "BTC-USD")
    if ohlcv is None:
        ohlcv = fetch_crypto_ohlcv(symbol=symbol)
    if ohlcv is None or ohlcv.empty:
        raise ValueError(f"{symbol}: no crypto OHLCV data available")

    snapshot = build_crypto_snapshot(ohlcv, now=now)
    if not snapshot:
        raise ValueError(f"{symbol}: not enough completed daily bars")

    target = decide_crypto_target(snapshot)
    action = build_rebalance_action(target["target_position_pct"], config)
    close = snapshot["close"]
    buy_limit = round(close * 1.003, 2) if close else None
    sell_limit = round(close * 0.997, 2) if close else None

    return {
        "enabled": True,
        "asset_class": "crypto",
        "symbol": symbol,
        "display_symbol": config.get("display_symbol", symbol),
        "broker": config.get("broker", "moomoo"),
        "policy": config.get("policy", DEFAULT_CRYPTO_CONFIG["policy"]),
        "fee_pct_per_side": config.get("fee_pct_per_side"),
        "snapshot": snapshot,
        "state": target["state"],
        "reason": target["reason"],
        "action": action,
        "execution_notes": {
            "preferred_signal_time": (
                "After the UTC daily candle closes; in US daylight time this "
                "is after 8:05 PM ET / 5:05 PM PT."
            ),
            "if_running_after_stock_close": (
                "Use the last completed UTC daily candle; do not trade from a "
                "partial BTC daily candle."
            ),
            "order_type": "Use limit orders; avoid chasing beyond the reference band.",
            "reference_buy_limit": buy_limit,
            "reference_sell_limit": sell_limit,
        },
        "production_impact": {
            "alters_stock_orders": False,
            "alters_crypto_orders": True,
            "shared_policy_changed": False,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "replay_only": False,
        },
    }
