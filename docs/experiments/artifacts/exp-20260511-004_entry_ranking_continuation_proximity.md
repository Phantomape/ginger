# exp-20260511-004 Entry Ranking Continuation Proximity

Hypothesis: ranking all same-day entry candidates by proximity to the 52-week high should allocate scarce slots to stronger continuation setups than the current breakout-only proximity ordering.

Decision: rejected. The all-signal ranking reduced EV and PnL in all three standard windows.

| Window | EV before | EV after | EV delta | PnL before | PnL after | Survival after | Trade count after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 3.7233 | -0.5107 | $94,086.91 | $80,071.89 | 84.31% | 19 |
| mid_weak | 1.6689 | 1.5977 | -0.0712 | $61,813.40 | $60,286.16 | 79.25% | 22 |
| old_thin | 0.3853 | 0.1930 | -0.1923 | $28,544.11 | $17,388.75 | 91.67% | 23 |

Protocol: `docs/backtesting.md` standard three non-overlapping windows with fixed OHLCV snapshots.

Single causal variable: replace the current breakout-only 52-week proximity re-ranking with an all-signal 52-week proximity ranking during same-day allocation.

Production impact: no promoted strategy code. A positive result would have required a shared policy change because `rank_signals_for_allocation` is used by both backtest and production paths. This rejected scout leaves production behavior unchanged.
