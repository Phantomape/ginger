# exp-20260511-010 TQS-Conditioned Sector Follower Risk

Decision: `promising_replay_only_underpowered`.

Hypothesis: the rejected same-day same-sector `risk_on` follower haircut was too
blunt because it cut crowded winners and losers. Existing relative
`trade_quality_score` should identify only lower-quality followers for a 0.5x
initial-risk haircut.

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Reduced | Kept followers | Changed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.3484 | +0.1144 | $94,086.91 | $95,568.55 | $+1,481.64 | 1 | 1 | 13 |
| mid_weak | 1.6689 | 1.6689 | +0.0000 | $61,813.40 | $61,813.40 | $+0.00 | 0 | 0 | 0 |
| old_thin | 0.3853 | 0.3853 | +0.0000 | $28,544.11 | $28,544.11 | $+0.00 | 0 | 0 | 0 |

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: apply the 0.5x same-day same-sector `risk_on` follower
risk haircut only when the follower's existing `trade_quality_score` is below
the first eligible same-sector leader's TQS. No entry filters, ranking,
universe membership, exits, stop/target rules, LLM/news behavior, or pilot
sleeves changed.

Gate notes:

- Gate 1: baseline rerun uses the accepted fixed-snapshot three-window protocol.
- Gate 2: no new production field; current `operator_inputs/open_positions.json`
  `entry_date` and `target_price` audit passed.
- Gate 3: no new entry filter; after survival-rate minimum is
  `0.7925`.
- Gate 4: `Shared promotion requires aggregate EV/PnL improvement, at least two EV-improved windows, no EV-regressed windows, survival-rate constraints, and a nonzero touched cohort. Positive one-window evidence is recorded as replay-only underpowered.`.

Production impact: replay-only alpha scout. No shared production/backtest policy
changed. A promoted version would need this exact rule in shared
`portfolio_engine.size_signals`, multiplier attribution in `backtester.py`, and
a focused parity test before any live/default sizing behavior changes.
