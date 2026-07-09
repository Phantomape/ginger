"""Broad-universe cross-sectional regime features (exp-20260709-004).

Read-only diagnostic infrastructure: daily cross-sectional dispersion and
average pairwise correlation over the liquid broad universe, plus generic
long-short decile proxy spreads (momentum, reversal) used as high-sample
outcome variables. Nothing here ranks candidates, sizes positions, or touches
orders; the TRADING universe stays the frozen core watchlist — this module
only widens the MEASUREMENT sample (exp-20260627 verdict).

Feature definitions (conventional, non-optimized):

- eligibility per day: close >= $5 and top ``TOP_N_LIQUID`` names by trailing
  20d average dollar volume;
- dispersion: cross-sectional std of same-day simple returns of the eligible
  set;
- average pairwise correlation: equal-weight portfolio variance identity over
  a trailing 20d return window — with N names, mean variance m and portfolio
  variance V, mean pairwise covariance C = (N*V - m) / (N - 1) and
  avg_corr = C / m (avoids ~320k explicit pairwise correlations);
- momentum proxy: rank eligible names at close t by their t-21 -> t-1 return,
  spread = mean next-day return of top decile minus bottom decile;
- reversal proxy: rank by day-t return, spread = bottom decile minus top
  decile next-day return.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

import numpy as np
import pandas as pd

FEATURES_RULE_VERSION = "broad_dispersion_corr_v1"

MIN_PRICE = 5.0
TOP_N_LIQUID = 800
ADV_WINDOW = 20
CORR_WINDOW = 20
MOM_LOOKBACK = 20  # t-21 -> t-1 (skip the last day to avoid reversal bleed)
DECILE = 10


def load_broad_panel(
    warehouse_paths: list[str],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(closes, dollar_volume) wide frames indexed by date, columns=tickers."""
    chunks: list[pd.DataFrame] = []
    for wh in warehouse_paths:
        con = sqlite3.connect(f"file:{wh}?mode=ro", uri=True)
        try:
            chunk = pd.read_sql_query(
                "select ticker, date, close, volume from ohlcv "
                "where date >= ? and date <= ? and close > 0",
                con,
                params=(start, end),
            )
        finally:
            con.close()
        if not chunk.empty:
            chunks.append(chunk)
    if not chunks:
        empty = pd.DataFrame()
        return empty, empty
    rows = pd.concat(chunks, ignore_index=True)
    rows["ticker"] = rows["ticker"].str.upper()
    rows["date"] = rows["date"].str.slice(0, 10)
    rows["dollar"] = rows["close"] * rows["volume"].fillna(0.0)
    # later warehouses win on duplicate (date, ticker)
    rows = rows.drop_duplicates(subset=["date", "ticker"], keep="last")
    closes = rows.pivot(index="date", columns="ticker", values="close").sort_index()
    dollar = rows.pivot(index="date", columns="ticker", values="dollar").sort_index()
    return closes, dollar


def liquidity_mask(closes: pd.DataFrame, dollar: pd.DataFrame) -> pd.DataFrame:
    """True where a name is eligible that day (price + rolling ADV rank)."""
    adv = dollar.rolling(ADV_WINDOW, min_periods=ADV_WINDOW).mean()
    price_ok = closes >= MIN_PRICE
    ranks = adv.where(price_ok).rank(axis=1, ascending=False)
    return (ranks <= TOP_N_LIQUID) & price_ok & adv.notna()


def daily_returns(closes: pd.DataFrame) -> pd.DataFrame:
    return closes.pct_change()


def cross_sectional_dispersion(returns: pd.DataFrame, mask: pd.DataFrame) -> pd.Series:
    """Per-day std of eligible same-day returns."""
    eligible = returns.where(mask)
    return eligible.std(axis=1, ddof=0)


def avg_pairwise_correlation(returns: pd.DataFrame, mask: pd.DataFrame) -> pd.Series:
    """Equal-weight portfolio variance identity over trailing CORR_WINDOW days.

    Names must be eligible on the anchor day and have a full return window.
    """
    values = returns.to_numpy(dtype=float)
    mask_np = mask.to_numpy(dtype=bool)
    out = np.full(len(returns), np.nan)
    for i in range(CORR_WINDOW, len(returns)):
        cols = mask_np[i]
        if not cols.any():
            continue
        window = values[i - CORR_WINDOW + 1 : i + 1][:, cols]
        full = ~np.isnan(window).any(axis=0)
        window = window[:, full]
        n = window.shape[1]
        if n < 30:
            continue
        variances = window.var(axis=0)
        mean_var = float(variances.mean())
        if mean_var <= 0:
            continue
        port_var = float(window.mean(axis=1).var())
        mean_cov = (n * port_var - mean_var) / (n - 1)
        out[i] = mean_cov / mean_var
    return pd.Series(out, index=returns.index)


def _decile_spread(
    returns: pd.DataFrame,
    signal: pd.DataFrame,
    mask: pd.DataFrame,
    *,
    long_top: bool,
) -> pd.Series:
    """Next-day equal-weight decile spread of ``signal`` within the mask.

    Value at index t is the day-(t+1) return of the spread formed at close t.
    """
    sig = signal.where(mask)
    next_ret = returns.shift(-1)
    out = np.full(len(returns), np.nan)
    sig_np = sig.to_numpy(dtype=float)
    nxt_np = next_ret.to_numpy(dtype=float)
    for i in range(len(returns)):
        row = sig_np[i]
        valid = ~np.isnan(row) & ~np.isnan(nxt_np[i])
        n = int(valid.sum())
        if n < 50:
            continue
        vals = row[valid]
        rets = nxt_np[i][valid]
        k = max(n // DECILE, 5)
        order = np.argsort(vals)
        bottom = rets[order[:k]].mean()
        top = rets[order[-k:]].mean()
        out[i] = (top - bottom) if long_top else (bottom - top)
    return pd.Series(out, index=returns.index)


def momentum_spread_next_day(
    returns: pd.DataFrame, closes: pd.DataFrame, mask: pd.DataFrame
) -> pd.Series:
    """20d momentum (t-21 -> t-1) decile spread, next-day payoff."""
    mom = closes.shift(1) / closes.shift(MOM_LOOKBACK + 1) - 1.0
    return _decile_spread(returns, mom, mask, long_top=True)


def reversal_spread_next_day(
    returns: pd.DataFrame, mask: pd.DataFrame
) -> pd.Series:
    """1d reversal decile spread (long yesterday's losers), next-day payoff."""
    return _decile_spread(returns, returns, mask, long_top=False)


# --------------------------------------------------------------------------- #
# Stats helpers (pure)
# --------------------------------------------------------------------------- #
def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 10:
        return None
    xs = pd.Series(x).rank().to_numpy()
    ys = pd.Series(y).rank().to_numpy()
    xm, ym = xs - xs.mean(), ys - ys.mean()
    denom = math.sqrt(float((xm**2).sum()) * float((ym**2).sum()))
    if denom <= 0:
        return None
    return float((xm * ym).sum()) / denom


def corr_t_stat(r: float | None, n: int) -> float | None:
    if r is None or n < 10 or abs(r) >= 1:
        return None
    return r * math.sqrt((n - 2) / (1.0 - r * r))


def quartile_means(feature: pd.Series, outcome: pd.Series) -> dict[str, Any]:
    frame = pd.DataFrame({"f": feature, "o": outcome}).dropna()
    if len(frame) < 40:
        return {"n": len(frame), "quartile_mean_bps": None}
    frame["q"] = pd.qcut(frame["f"], 4, labels=False, duplicates="drop")
    means = frame.groupby("q")["o"].mean() * 10000.0
    return {
        "n": int(len(frame)),
        "quartile_mean_bps": {f"q{int(k) + 1}": round(float(v), 2) for k, v in means.items()},
        "q4_minus_q1_bps": round(float(means.iloc[-1] - means.iloc[0]), 2),
    }
