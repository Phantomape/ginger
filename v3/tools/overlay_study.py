"""Pre-registered one-shot study: does a trend exit reduce single-stock losses?  (A in the 10-10 plan)

Registration: v3/strategies/REGISTRATION_A_20261010.md (study A).  The script refuses to run a
second time once its output exists, so the result cannot be re-rolled.

Rule (same as S1, applied per stock): at each month end, hold the stock if its total-return index
is above its 200-day average, otherwise cash; fill at the next close.  Comparison: holding the same
stock over the same days.  Costs: 10 bp per side plus $1 per order on $100k / 37 per stock.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3 / "evaluator"))
sys.path.insert(0, str(V3 / "data"))
import data  # noqa: E402
import engine  # noqa: E402
import metrics  # noqa: E402
from fetch import STOCKS  # noqa: E402

OUT = V3 / "ledger" / "overlay_study_A.json"
START, END = "1994-03-01", "2026-06-30"
SMA_DAYS = 200
CAPITAL_PER_STOCK = 100_000 / len(STOCKS)
PLACEBO_DRAWS = 1000
SEED = 20261010
# pre-registered pass criteria (portfolio = equal weight across available stocks, daily)
MIN_MAXDD_IMPROVEMENT = 0.10   # P1: timed max drawdown at least 10 points shallower
MAX_RETURN_COST = 0.02         # P3: timed annual return at most 2 points below holding
PLACEBO_PCTL = 0.95            # P4: rule beats 95% of random-timing placebos on drawdown


def stock_panel() -> tuple[pd.DataFrame, pd.Series]:
    _, cash = data.etf_panel()
    cols = {t: data.total_return(data._read(f"raw/stocks/{t}.csv")) for t in STOCKS}
    panel = pd.DataFrame(cols).reindex(cash.index)
    return panel, cash


def rule(asset):
    def signal(hist):
        r = hist.returns[asset].dropna()
        if len(r) < SMA_DAYS:
            return {}
        tri = (1 + r).cumprod()
        return {asset: 1.0} if tri.iloc[-1] > tri.iloc[-SMA_DAYS:].mean() else {}
    return signal


def first_decision(r: pd.Series) -> pd.Timestamp | None:
    valid = r.dropna()
    if len(valid) < SMA_DAYS:
        return None
    return max(pd.Timestamp(START), valid.index[SMA_DAYS - 1])


def run_pair(asset, panel, cash):
    start = first_decision(panel[asset])
    p, c = panel[[asset]].loc[:END], cash.loc[:END]
    kw = dict(start=start, end=END, freq="M", cost_kind="stock", exec_lag=1, capital=CAPITAL_PER_STOCK)
    timed = engine.run(rule(asset), p, c, **kw)
    first = min(timed.weights) if timed.weights else None
    # holding starts on the timed rule's first fill date so both cover the same days
    hold = engine.run(lambda h: {asset: 1.0}, p, c, **kw)
    return timed, hold, first


def monthly_positions(timed_weights: dict, days: pd.DatetimeIndex) -> pd.Series:
    """Daily in/out exposure implied by the executed fills (exposure starts the day after a fill)."""
    pos = pd.Series(np.nan, index=days)
    for d, w in timed_weights.items():
        nxt = days[days > d]
        if len(nxt):
            pos.loc[nxt[0]] = 1.0 if w else 0.0
    return pos.ffill().fillna(0.0)


def placebo_returns(r: pd.Series, c: pd.Series, pos: pd.Series, rng, draws: int) -> np.ndarray:
    """Circularly shift the rule's monthly in/out pattern: same time in market and run lengths,
    random timing.  Costs charged on switches at 10 bp per side (fee approximated at start capital)."""
    months = pos.index.to_period("M")
    m_pos = pos.groupby(months).last().values  # exposure after that month's decision
    month_idx = pd.factorize(months)[0]
    rv, cv = r.fillna(0.0).values, c.values
    out = np.empty((draws, len(r)))
    for k in range(draws):
        shifted = np.roll(m_pos, rng.integers(1, len(m_pos)))[month_idx]
        switch = np.abs(np.diff(shifted, prepend=shifted[0]))
        cost = switch * (10e-4 + 1.0 / CAPITAL_PER_STOCK)
        out[k] = (1 + np.where(shifted > 0, rv, cv)) * (1 - cost) - 1
    return out


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: this study is one-shot and has already been run")
    panel, cash = stock_panel()
    rng = np.random.default_rng(SEED)
    per_stock, timed_cols, hold_cols, placebo_sum, placebo_n = {}, {}, {}, None, None
    for t in STOCKS:
        if first_decision(panel[t]) is None or first_decision(panel[t]) > pd.Timestamp(END):
            continue
        timed, hold, first = run_pair(t, panel, cash)
        if first is None:
            continue
        tn, hn = timed.net.loc[first:], hold.net.loc[first:]
        timed_cols[t], hold_cols[t] = tn, hn
        c = cash.reindex(tn.index)
        per_stock[t] = {
            "start": str(first.date()), "years": round(len(tn) / 252, 1),
            "maxdd_timed": metrics.max_drawdown(tn), "maxdd_hold": metrics.max_drawdown(hn),
            "ann_timed": float((1 + tn).prod() ** (252 / len(tn)) - 1),
            "ann_hold": float((1 + hn).prod() ** (252 / len(hn)) - 1),
            "sharpe_timed": metrics.sharpe(tn, c), "sharpe_hold": metrics.sharpe(hn, c),
            "time_in_market": float(monthly_positions(timed.weights, tn.index).mean()),
        }
        pos = monthly_positions(timed.weights, tn.index)
        pl = placebo_returns(panel[t].reindex(tn.index), c, pos, rng, PLACEBO_DRAWS)
        pl_df = pd.DataFrame(pl.T, index=tn.index)
        placebo_sum = pl_df if placebo_sum is None else placebo_sum.add(pl_df, fill_value=0.0)
        ones = pd.Series(1.0, index=tn.index)
        placebo_n = ones if placebo_n is None else placebo_n.add(ones, fill_value=0.0)

    timed_ew = pd.DataFrame(timed_cols).mean(axis=1, skipna=True)
    hold_ew = pd.DataFrame(hold_cols).mean(axis=1, skipna=True)
    placebo_ew = placebo_sum.div(placebo_n, axis=0)
    c = cash.reindex(timed_ew.index)

    def roll12_min(x):
        return float(((1 + x).rolling(252).apply(np.prod, raw=True) - 1).min())

    dd_t, dd_h = metrics.max_drawdown(timed_ew), metrics.max_drawdown(hold_ew)
    ann_t = float((1 + timed_ew).prod() ** (252 / len(timed_ew)) - 1)
    ann_h = float((1 + hold_ew).prod() ** (252 / len(hold_ew)) - 1)
    placebo_dd = np.array([metrics.max_drawdown(placebo_ew[k]) for k in placebo_ew.columns])
    pctl = float((placebo_dd < dd_t).mean())  # share of placebos with a deeper drawdown
    portfolio = {
        "start": str(timed_ew.index[0].date()), "end": str(timed_ew.index[-1].date()),
        "maxdd_timed": dd_t, "maxdd_hold": dd_h, "ann_timed": ann_t, "ann_hold": ann_h,
        "sharpe_timed": metrics.sharpe(timed_ew, c), "sharpe_hold": metrics.sharpe(hold_ew, c),
        "worst_12m_timed": roll12_min(timed_ew), "worst_12m_hold": roll12_min(hold_ew),
        "placebo_share_with_deeper_drawdown": pctl,
        "placebo_maxdd_median": float(np.median(placebo_dd)),
    }
    criteria = {
        "P1_maxdd_improvement_ge_10pt": dd_t - dd_h >= MIN_MAXDD_IMPROVEMENT,
        "P2_worst_12m_better": portfolio["worst_12m_timed"] > portfolio["worst_12m_hold"],
        "P3_return_cost_le_2pt": ann_t >= ann_h - MAX_RETURN_COST,
        "P4_beats_95pct_placebos_on_drawdown": pctl >= PLACEBO_PCTL,
    }
    med = {k: float(np.median([v[k] for v in per_stock.values()]))
           for k in ("maxdd_timed", "maxdd_hold", "ann_timed", "ann_hold", "sharpe_timed", "sharpe_hold", "time_in_market")}
    result = {
        "at_utc": datetime.now(timezone.utc).isoformat(), "stocks": len(per_stock),
        "portfolio": portfolio, "criteria": criteria, "passed": all(criteria.values()),
        "per_stock_median": med, "per_stock": per_stock,
    }
    OUT.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("stocks", "portfolio", "criteria", "passed", "per_stock_median")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
