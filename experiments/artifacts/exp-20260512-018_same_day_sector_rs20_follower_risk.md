# exp-20260512-018: Same-Day Sector RS20 Follower Risk

Decision: `rejected_replay_only`.

Hypothesis: in same-day same-sector core A/B clusters, the native first candidate
should keep its current sizing, but a later same-sector candidate whose
20-trading-day return versus SPY is lower than that first candidate may deserve
a smaller initial risk budget.

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Reduced | Kept | Changed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2251 | -0.0089 | $94,086.91 | $93,269.05 | $-817.86 | 3 | 1 | 13 |
| mid_weak | 1.6689 | 1.6689 | +0.0000 | $61,813.40 | $61,813.40 | $+0.00 | 0 | 1 | 0 |
| old_thin | 0.3853 | 0.3853 | +0.0000 | $28,544.11 | $28,544.11 | $+0.00 | 2 | 2 | 0 |

Aggregate EV delta: `-0.0089`.
Aggregate PnL delta: `$-817.86`.

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: apply a 0.5x share/risk haircut to second-and-later
same-day same-sector `trend_long` / `breakout_long` signals only when the
follower's existing `ticker_ret20_minus_spy_pct` is below that sector's first
same-day core signal. No entry generation, ranking, universe membership, exits,
stops, targets, add-ons, event sleeves, or LLM/news behavior changed.

Gate notes:

- Gate 1: baseline and variant reran all three fixed windows.
- Gate 2: `operator_inputs/open_positions.json` required-field audit passed.
- Gate 3: no new entry filter; minimum after survival rate was `0.7925`.
- Gate 4: `Shared promotion requires aggregate EV/PnL improvement, at least two EV-improved windows, no EV-regressed windows, survival-rate constraints, max drawdown damage <= 2 pp, and a nonzero touched cohort.`

Production impact: replay-only. If a future version is accepted, the rule must
be moved into shared production/backtest sizing policy before it can affect
orders.
