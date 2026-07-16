# exp-20260716-002: Treasury indirect-bidder-share TBT

- Status: `rejected`
- Decision: `rejected_indirect_bidder_tbt_edge_not_robust`
- Account: standalone fully funded $100,000 paper account; core PnL is not added
- Production orders changed: no

| Window | Trades | PnL | EV | Mean cash repl. | Mean QQQ repl. | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| old_thin | 14 | $-4,406.32 | 0.1191 | $-314.74 | $-245.96 | 0.0502 |
| mid_weak | 13 | $-2,526.56 | 0.0466 | $-194.35 | $-465.56 | 0.0363 |
| late_strong | 13 | $398.25 | 0.0017 | $30.63 | $-15.65 | 0.0108 |

- Aggregate standalone EV: `0.1674`
- Aggregate standalone PnL: `$-6,534.63`
- DSR: `computed` / `0.021314996240211936`
- Complete two-rule panel: `True`
- Failed checks: `all_window_pnl_nonnegative, all_window_cash_replacement_positive, all_window_qqq_replacement_positive, aggregate_ev_beats_accepted_comparator, aggregate_pnl_beats_accepted_comparator, drawdown_passed, dsr_passed, top_tenor_concentration_passed`
- Interpretation: The fixed participant-composition signal lost money in old_thin and mid_weak and had negative QQQ replacement value in all three windows. Its positive aggregate EV number is only the sign artifact of multiplying a negative return by a negative Sharpe in losing windows; the independent PnL and replacement-value gates correctly prevent promotion.

## Boundary

Do not retune indirect-share threshold, lookback, tenor subset, entry, hold, TBT proxy, cost, overlap, response shape or notional on these frozen auction rows.

No JavaScript was used.
