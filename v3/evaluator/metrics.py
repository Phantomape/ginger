"""Frozen V3 metrics: Sharpe, drawdown, PSR/DSR, vol-matched excess, threshold reachability.

PSR/DSR follow docs/deflated_sharpe_protocol.md (periodic Sharpe, Pearson kurtosis).
V3 uses the null dispersion of Sharpe estimates, sigma = 1/sqrt(T) periodic, for the
expected-maximum benchmark: it is computable for any trial count and does not reward
correlated variants (those are already counted twice by the budget rule).
"""
from __future__ import annotations

import math
from statistics import NormalDist

import pandas as pd

EULER_GAMMA = 0.5772156649015329
_N = NormalDist()


def periods_per_year(index: pd.DatetimeIndex) -> int:
    return 252 if pd.Series(index).diff().median() <= pd.Timedelta(days=5) else 12


def max_drawdown(r: pd.Series) -> float:
    nav = (1 + r).cumprod()
    return float((nav / nav.cummax() - 1).min())


def sharpe(r: pd.Series, cash: pd.Series) -> float:
    ex = (r - cash.reindex(r.index).fillna(0.0)).dropna()
    sd = ex.std()
    return float(ex.mean() / sd * math.sqrt(periods_per_year(r.index))) if sd > 0 else 0.0


def psr(ex: pd.Series, sr_star_periodic: float = 0.0) -> float:
    ex = ex.dropna()
    t = len(ex)
    sd = ex.std()
    if t < 3 or sd == 0:
        return float("nan")
    sr = ex.mean() / sd
    skew = float(((ex - ex.mean()) ** 3).mean() / ex.std(ddof=0) ** 3)
    kurt = float(((ex - ex.mean()) ** 4).mean() / ex.std(ddof=0) ** 4)
    q = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    return _N.cdf((sr - sr_star_periodic) * math.sqrt(t - 1) / math.sqrt(q))


def expected_max_sr(sigma_periodic: float, n: int) -> float:
    if n <= 1:
        return 0.0
    return sigma_periodic * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n)
                             + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n * math.e)))


def dsr(ex: pd.Series, n_trials: int) -> float:
    t = len(ex.dropna())
    return psr(ex, expected_max_sr(1 / math.sqrt(t), n_trials))


def required_sharpe(years: float, ppy: int, n_trials: int, conf: float = 0.95) -> float:
    """Annual Sharpe needed for DSR >= conf under normal returns."""
    t = years * ppy
    sr0 = expected_max_sr(1 / math.sqrt(t), n_trials)
    return (sr0 + _N.inv_cdf(conf) / math.sqrt(t - 1)) * math.sqrt(ppy)


def vol_matched(r: pd.Series, bench: pd.Series, cash: pd.Series) -> dict:
    """Compare r with bench scaled (bench excess x k, rest in cash) to r's volatility."""
    c = cash.reindex(r.index).fillna(0.0)
    b = bench.reindex(r.index)
    k = (r - c).std() / (b - c).std()
    matched = c + k * (b - c)
    ppy = periods_per_year(r.index)
    return {
        "k": float(k),
        "excess_ann": float((r - matched).mean() * ppy),
        "strategy_maxdd": max_drawdown(r),
        "matched_maxdd": max_drawdown(matched),
    }


def summary(r: pd.Series, cash: pd.Series) -> dict:
    ppy = periods_per_year(r.index)
    years = len(r) / ppy
    ex = r - cash.reindex(r.index).fillna(0.0)
    return {
        "start": str(r.index[0].date()),
        "end": str(r.index[-1].date()),
        "years": round(years, 2),
        "ann_return": float((1 + r).prod() ** (1 / years) - 1),
        "ann_vol": float(r.std() * math.sqrt(ppy)),
        "sharpe": sharpe(r, cash),
        "max_drawdown": max_drawdown(r),
        "psr0": psr(ex),
    }


def reachability_table(rows: list[tuple[str, float, int]], trials=(1, 4, 12, 24, 48)) -> str:
    lines = ["| 样本 | 年数 | " + " | ".join(f"N={n}" for n in trials) + " |",
             "|---|--:|" + "--:|" * len(trials)]
    for name, years, ppy in rows:
        cells = " | ".join(f"{required_sharpe(years, ppy, n):.2f}" for n in trials)
        lines.append(f"| {name} | {years:.1f} | {cells} |")
    return "\n".join(lines)
