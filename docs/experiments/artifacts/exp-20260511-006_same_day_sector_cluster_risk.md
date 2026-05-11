# exp-20260511-006 Same-Day Sector Cluster Risk

Decision: `rejected_replay_only`.

Hypothesis: when the core engine creates multiple same-day, same-sector `risk_on` entries that already carry unmodified risk-on sizing, the second and later entries may have worse tail exposure and should receive a smaller initial risk budget.

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Adjusted signals | Changed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2251 | -0.0089 | $94,086.91 | $93,269.05 | $-817.86 | 2 | 13 |
| mid_weak | 1.6689 | 1.6689 | +0.0000 | $61,813.40 | $61,813.40 | $+0.00 | 0 | 0 |
| old_thin | 0.3853 | 0.3853 | +0.0000 | $28,544.11 | $28,544.11 | $+0.00 | 0 | 0 |

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: 0.5x follower sizing for second-and-later same-day same-sector `risk_on` core entries. No entry filters, ranking, universe membership, exits, stop/target rules, LLM/news behavior, or pilot sleeves changed.

Gate notes:

- Gate 1: baseline rerun uses the accepted fixed-snapshot three-window protocol.
- Gate 2: no new runtime fields; current `operator_inputs/open_positions.json` `entry_date` and `target_price` audit passed.
- Gate 3: no new entry filter; after survival-rate minimum is `0.7925`.
- Gate 4: `Accept only if aggregate EV/PnL improve, at least two windows improve EV, no window regresses EV, and survival-rate constraints hold.`.

Production impact: replay-only scout. A positive result would need the same follower-risk rule implemented in shared `portfolio_engine.size_signals`, with the new multiplier key added to shared backtest attribution and a focused parity test before live/default behavior changes.
