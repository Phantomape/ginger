"""Synthetic tests for the frozen V3 evaluator.  These prove program behaviour, not profit."""
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3 / "evaluator"))
sys.path.insert(0, str(V3 / "portfolio"))
import baselines  # noqa: E402
import data  # noqa: E402
import engine  # noqa: E402
import metrics  # noqa: E402
from combine import portfolio_signal  # noqa: E402

DAYS = pd.bdate_range("2020-01-01", "2021-12-31")


def panel(**cols):
    return pd.DataFrame({k: pd.Series(v, index=DAYS) for k, v in cols.items()})


ZERO_CASH = pd.Series(0.0, index=DAYS)


def hold(asset, w=1.0):
    return lambda hist: {asset: w}


def test_constant_prices_lose_only_costs():
    res = engine.run(hold("A"), panel(A=0.0), ZERO_CASH, start=DAYS[0], end=DAYS[-1])
    # one buy order: 3 bp of notional + $1 on $100k; holding the same weight later costs nothing
    assert res.cost.sum() == pytest.approx(3e-4 + 1 / 100_000, rel=1e-6)
    assert (1 + res.net).prod() - 1 == pytest.approx(-(3e-4 + 1e-5), rel=1e-6)
    assert res.gross.abs().max() == 0


def test_known_trend_known_direction():
    res = engine.run(hold("A"), panel(A=0.001), ZERO_CASH, start=DAYS[0], end=DAYS[-1])
    # invested from the day after the first trade fills
    assert res.net.iloc[-1] == pytest.approx(0.001)
    assert metrics.summary(res.net, ZERO_CASH)["ann_return"] > 0.2

    def momentum(hist):
        r = hist.returns.iloc[-20:].sum()
        return {"A": 1.0} if r["A"] > r["B"] else {"B": 1.0}

    res = engine.run(momentum, panel(A=0.001, B=-0.001), ZERO_CASH, start=DAYS[30], end=DAYS[-1])
    assert all(w == {"A": 1.0} for w in res.weights.values())


def test_missing_returns():
    rets = panel(A=0.0, B=0.0)
    rets.loc[DAYS[100], "B"] = float("nan")
    engine.run(hold("A"), rets, ZERO_CASH, start=DAYS[0], end=DAYS[-1])  # B unheld: fine
    with pytest.raises(ValueError, match="return is missing"):
        engine.run(hold("B"), rets, ZERO_CASH, start=DAYS[0], end=DAYS[-1])


def test_dividends_and_split_adjusted_closes():
    df = pd.DataFrame({
        "date": ["2020-01-02", "2020-01-03", "2020-01-06"],
        "close": [100.0, 100.0, 50.0 * 2],  # yfinance closes are already split-adjusted
        "dividend": [0.0, 1.0, 0.0], "capital_gain": [0.0, 0.0, 0.5], "split": [0.0, 0.0, 2.0],
    })
    r = data.total_return(df)
    assert r.iloc[1] == pytest.approx(0.01)
    assert r.iloc[2] == pytest.approx(0.005)


def test_no_leverage_no_shorts_so_cash_never_negative():
    with pytest.raises(ValueError, match="no leverage"):
        engine.run(lambda h: {"A": 0.7, "B": 0.4}, panel(A=0.0, B=0.0), ZERO_CASH, start=DAYS[0], end=DAYS[-1])
    with pytest.raises(ValueError, match=">= 0"):
        engine.run(lambda h: {"A": -0.5}, panel(A=0.0), ZERO_CASH, start=DAYS[0], end=DAYS[-1])
    with pytest.raises(ValueError, match="unknown asset"):
        engine.run(hold("Z"), panel(A=0.0), ZERO_CASH, start=DAYS[0], end=DAYS[-1])


def test_cash_earns_cash_rate():
    cash = pd.Series(0.0001, index=DAYS)
    res = engine.run(hold("A", 0.5), panel(A=0.0), cash, start=DAYS[0], end=DAYS[-1])
    # cash share drifts slightly above 50% between rebalances as cash accrues
    assert res.gross.iloc[-1] == pytest.approx(0.5 * 0.0001, rel=0.01)


def test_no_lookahead_and_execution_lag():
    seen = []

    def spy(hist):
        seen.append(hist.returns.index[-1])
        return {"A": 1.0}

    rets = panel(A=0.0)
    first_rebal = DAYS[DAYS.to_period("M") == DAYS[0].to_period("M")][-1]
    nxt = DAYS[DAYS.get_loc(first_rebal) + 1]
    rets.loc[nxt, "A"] = 0.5  # jump on the fill day must not be earned
    res = engine.run(spy, rets, ZERO_CASH, start=DAYS[0], end=DAYS[-1])
    assert seen[0] == first_rebal
    assert all(s in engine.rebalance_dates(DAYS, "M") for s in seen)
    assert res.gross.loc[nxt] == 0
    assert list(res.weights)[0] == nxt


def test_daily_signals_fill_every_session():
    # each daily decision fills at the next close; the next decision must not overwrite it
    flip = lambda hist: {"A": 1.0} if len(hist.returns) % 2 else {}
    res = engine.run(flip, panel(A=[0.001] * len(DAYS)), ZERO_CASH, start=DAYS[0], end=DAYS[-1], freq="D")
    fills = list(res.weights.items())
    assert len(fills) == len(DAYS) - 1
    for j, (d, w) in enumerate(fills, start=1):
        assert d == DAYS[j]
        assert w == ({"A": 1.0} if j % 2 else {})


def test_monthly_same_close_execution():
    months = pd.date_range("2000-01-31", periods=24, freq="ME")
    rets = pd.DataFrame({"A": 0.01}, index=months)
    res = engine.run(hold("A"), rets, pd.Series(0.0, index=months), start=months[0], end=months[-1],
                     cost_kind="evidence", exec_lag=0)
    assert res.gross.iloc[1] == pytest.approx(0.01)
    assert res.cost.iloc[0] == pytest.approx(10e-4 + 1e-5)


def test_psr_and_reachability_are_consistent():
    # a return series whose annual Sharpe equals the required value gives PSR ~= 0.95 for N=1
    years, ppy = 20, 252
    need = metrics.required_sharpe(years, ppy, 1)
    n = years * ppy
    x = pd.Series([1.0 if i % 2 else -1.0 for i in range(n)])
    ex = x * 0.01 + need / math.sqrt(ppy) * 0.01
    assert metrics.psr(ex) == pytest.approx(0.95, abs=0.01)
    assert metrics.required_sharpe(9.5, 252, 48) > metrics.required_sharpe(9.5, 252, 1)
    assert metrics.expected_max_sr(0.1, 1) == 0


def test_baseline_200dma():
    up = panel(SPY=0.001)
    down = panel(SPY=-0.001)
    hist_up = engine.History(up, ZERO_CASH)
    hist_down = engine.History(down, ZERO_CASH)
    assert baselines.s1_spy_200dma(hist_up) == {"SPY": 1.0}
    assert baselines.s1_spy_200dma(hist_down) == {}


def test_portfolio_caps_and_vol_target():
    import numpy as np

    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0, 0.02, (len(DAYS), 3)), index=DAYS, columns=["A", "B", "C"])
    w = portfolio_signal([hold("A"), hold("B")])(engine.History(rets, ZERO_CASH))
    assert max(w.values()) <= 0.25 + 1e-12 and sum(w.values()) <= 1 + 1e-12
    calm = rets * 0.05
    w2 = portfolio_signal([lambda h: {"A": 0.5, "B": 0.5}])(engine.History(calm, ZERO_CASH))
    assert w2 == pytest.approx({"A": 0.25, "B": 0.25})  # cannot lever up past the asset cap


def test_core_satellite_equal_risk():
    import numpy as np

    rng = np.random.default_rng(1)
    core = pd.Series(rng.normal(0, 0.02, len(DAYS)), index=DAYS)
    sat = pd.Series(rng.normal(0, 0.01, len(DAYS)), index=DAYS)
    combo = metrics.core_satellite(core, sat)
    w_core = (1 / core.std()) / (1 / core.std() + 1 / sat.std())
    assert combo.iloc[5] == pytest.approx(w_core * core.iloc[5] + (1 - w_core) * sat.iloc[5])
    assert w_core == pytest.approx(1 / 3, abs=0.05)
    # an uncorrelated stream with the same Sharpe raises the combined Sharpe
    zero = pd.Series(0.0, index=DAYS)
    a = pd.Series(rng.normal(0.001, 0.01, len(DAYS)), index=DAYS)
    b = pd.Series(rng.normal(0.001, 0.01, len(DAYS)), index=DAYS)
    assert metrics.sharpe(metrics.core_satellite(a, b), zero) > metrics.sharpe(a, zero)


def test_holding_cost_for_sorted_portfolios():
    months = pd.date_range("2000-01-31", periods=24, freq="ME")
    rets = pd.DataFrame({"MOM:Hi PRIOR": 0.0}, index=months)
    res = engine.run(hold("MOM:Hi PRIOR"), rets, pd.Series(0.0, index=months), start=months[0], end=months[-1],
                     cost_kind="evidence", exec_lag=0, holding_cost_annual={"MOM:Hi PRIOR": 0.03})
    # after the first month the only cost is 3%/12 per month on a full position
    assert res.cost.iloc[5] == pytest.approx(0.03 / 12)
    res2 = engine.run(hold("MOM:Hi PRIOR"), rets, pd.Series(0.0, index=months), start=months[0], end=months[-1],
                      cost_kind="evidence", exec_lag=0, cost_mult=2.0, holding_cost_annual={"MOM:Hi PRIOR": 0.03})
    assert res2.cost.iloc[5] == pytest.approx(0.06 / 12)


def test_trim_to_first_holding():
    import evaluate

    def late(hist):
        return {"A": 1.0} if len(hist.returns) > 100 else {}

    res = engine.run(late, panel(A=0.001), ZERO_CASH, start=DAYS[0], end=DAYS[-1])
    trimmed, first = evaluate.trim_to_first_holding(res)
    assert first == min(d for d, w in res.weights.items() if w)
    assert trimmed.net.index[0] == first and len(trimmed.net) < len(res.net)


def test_sorts_panel_columns():
    import evaluate

    lock = evaluate.verify_lock()
    so, rf = data.sorts_panel({k: v["path"] for k, v in lock["french"].items()})
    for col in ("MOM:Hi PRIOR", "OP:Hi 10", "INV:Lo 10", "BM:Hi 10", "MKT"):
        assert col in so.columns
    assert so["MOM:Hi PRIOR"].first_valid_index().year == 1927
    assert so["OP:Hi 10"].first_valid_index().year == 1963


def test_active_vs_market_removes_beta():
    import numpy as np

    rng = np.random.default_rng(2)
    mkt = pd.Series(rng.normal(0.0004, 0.01, len(DAYS)), index=DAYS)
    levered = 0.5 * mkt  # pure market exposure at half the risk: no excess return
    act = metrics.active_vs_market(levered, mkt, ZERO_CASH)
    assert act.abs().max() < 1e-12
    alpha = mkt * 0.5 + 0.0002
    assert metrics.active_vs_market(alpha, mkt, ZERO_CASH).mean() == pytest.approx(0.0002, rel=1e-6)
