# exp-20260511-013 All-Core TQS Sector Follower Risk

Decision: `rejected_replay_only`.

Hypothesis: same-day same-sector core entry clusters are not all bad, but lower
TQS followers may deserve a smaller initial risk budget even outside the
previous risk-on-only cohort.

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Reduced | Kept | Changed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.3484 | +0.1144 | $94,086.91 | $95,568.55 | $+1,481.64 | 1 | 3 | 13 |
| mid_weak | 1.6689 | 1.6689 | +0.0000 | $61,813.40 | $61,813.40 | $+0.00 | 1 | 0 | 0 |
| old_thin | 0.3853 | 0.3449 | -0.0404 | $28,544.11 | $26,532.81 | $-2,011.30 | 2 | 2 | 5 |

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: apply a 0.5x initial-risk haircut to second-and-later
same-day same-sector core A/B signals only when the follower's existing
`trade_quality_score` is below that sector's first same-day core signal. No
entry filters, ranking, universe membership, exits, stop/target rules,
LLM/news behavior, pilot sleeves, or TQS thresholds changed.

Gate notes:

- Gate 1: baseline rerun uses the accepted fixed-snapshot three-window protocol.
- Gate 2: no new runtime field; current `operator_inputs/open_positions.json`
  `entry_date` and `target_price` audit passed.
- Gate 3: no new entry filter; after survival-rate minimum is
  `0.7925`.
- Gate 4: `Shared promotion requires aggregate EV/PnL improvement, at least two EV-improved windows, no EV-regressed windows, survival-rate constraints, max drawdown damage <= 2 pp, and a nonzero touched cohort.`.

Production impact: replay-only alpha scout unless Gate 4 accepts shared-policy
implementation. A promoted version must live in shared `portfolio_engine`, add
the multiplier to backtest attribution, and add a focused parity test.
