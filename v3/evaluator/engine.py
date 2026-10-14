"""Frozen V3 backtest engine and cost model.

Contract:
* A strategy is ``signal(hist) -> {asset: weight}``.  ``hist.returns`` / ``hist.cash`` hold
  only data up to and including the signal date.
* Long-only, weights >= 0 and sum <= 1; the rest is cash earning the cash rate.  Cash can
  therefore never go negative (the V1 overdraft bug class).
* Signals are taken on rebalance dates.  With ``exec_lag=1`` (daily data) the trade fills at
  the next session's close; with ``exec_lag=0`` (monthly evidence data) at the same close.
* Costs per trade: per-side bps of traded notional + a fixed per-order fee on the dollar NAV.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

COST_BPS_PER_SIDE = {"etf": 3.0, "stock": 10.0, "evidence": 10.0}
ORDER_FEE_USD = 1.0
CAPITAL_USD = 100_000.0
MIN_TRADE = 1e-6


@dataclass
class History:
    returns: pd.DataFrame
    cash: pd.Series


@dataclass
class Result:
    net: pd.Series
    gross: pd.Series
    cost: pd.Series
    turnover: pd.Series
    weights: dict = field(default_factory=dict)  # trade date -> executed weights


def rebalance_dates(index: pd.DatetimeIndex, freq: str) -> set:
    if freq == "D":
        return set(index)
    key = index.to_period(freq)
    s = pd.Series(index, index=index)
    return set(s.groupby(key).max())


def validate_weights(w: dict, columns) -> dict:
    out = {}
    for k, v in (w or {}).items():
        if k not in columns:
            raise ValueError(f"unknown asset {k!r}")
        v = float(v)
        if not math.isfinite(v) or v < 0:
            raise ValueError(f"weight for {k} must be finite and >= 0, got {v}")
        if v > 0:
            out[k] = v
    if sum(out.values()) > 1 + 1e-9:
        raise ValueError(f"weights sum to {sum(out.values()):.6f} > 1 (no leverage allowed)")
    return out


def _trade(weights: dict, target: dict, nav: float, bps: float, fee: float) -> tuple[float, float]:
    assets = set(target) | set(weights)
    trades = [target.get(a, 0.0) - weights.get(a, 0.0) for a in assets]
    turnover = sum(abs(t) for t in trades)
    n_orders = sum(1 for t in trades if abs(t) > MIN_TRADE)
    return turnover * bps + n_orders * fee / nav, turnover


def run(signal, returns: pd.DataFrame, cash: pd.Series, *, start, end, freq: str = "M",
        cost_kind: str = "etf", cost_mult: float = 1.0, exec_lag: int = 1,
        capital: float = CAPITAL_USD, holding_cost_annual: dict | None = None) -> Result:
    """``holding_cost_annual`` charges a per-asset annual rate on held weight each period: the
    trading cost of turnover inside a sorted portfolio, which the engine cannot observe."""
    bps = COST_BPS_PER_SIDE[cost_kind] * cost_mult / 1e4
    hold_rate = holding_cost_annual or {}
    ppy = 252 if pd.Series(returns.index).diff().median() <= pd.Timedelta(days=5) else 12
    fee = ORDER_FEE_USD * cost_mult
    dates = returns.index[(returns.index >= pd.Timestamp(start)) & (returns.index <= pd.Timestamp(end))]
    rebal = rebalance_dates(returns.index, freq)
    weights: dict = {}
    nav = capital
    pending: dict = {}  # position to execute at -> target; a later signal never overwrites an unfilled order
    net, gross, costs, turns, executed = [], [], [], [], {}
    for i, d in enumerate(dates):
        r = returns.loc[d]
        held = [a for a in weights if pd.isna(r[a])]
        if held:
            raise ValueError(f"{d.date()}: holding {held} but return is missing")
        hold_cost = sum(w * hold_rate.get(a, 0.0) for a, w in weights.items()) * cost_mult / ppy
        asset_val = {a: w * (1 + r[a]) for a, w in weights.items()}
        total = sum(asset_val.values()) + (1 - sum(weights.values())) * (1 + float(cash.loc[d]))
        weights = {a: v / total for a, v in asset_val.items()}
        nav *= total

        if d in rebal and i < len(dates) - 1:
            target = validate_weights(signal(History(returns.loc[:d], cash.loc[:d])), returns.columns)
            if i + exec_lag < len(dates):
                pending[i + exec_lag] = target
        cost_frac, turnover = hold_cost, 0.0
        nav *= 1 - hold_cost
        if i in pending:
            target = pending.pop(i)
            trade_cost, turnover = _trade(weights, target, nav, bps, fee)
            nav *= 1 - trade_cost
            cost_frac = 1 - (1 - hold_cost) * (1 - trade_cost)
            weights = dict(target)
            executed[d] = weights
        net.append(total * (1 - cost_frac) - 1)
        gross.append(total - 1)
        costs.append(cost_frac)
        turns.append(turnover)
    idx = pd.DatetimeIndex(dates)
    return Result(pd.Series(net, idx), pd.Series(gross, idx), pd.Series(costs, idx), pd.Series(turns, idx), executed)
