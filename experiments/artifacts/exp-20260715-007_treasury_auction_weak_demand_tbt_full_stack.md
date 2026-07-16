# exp-20260715-007: Treasury auction weak-demand TBT

- Status: `rejected`
- Decision: `rejected_treasury_auction_tbt_edge_not_robust`
- Production orders changed: no
- Policy: prior-12 same-tenor BTC median, strict next open, one $16k TBT position, fifth-session close

| Window | Trades | Mean TBT net | Mean cash repl. | Mean QQQ repl. | EV delta | PnL delta | Max-DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| old_thin | 11 | -0.018304 | $-292.87 | $-394.21 | -0.1859 | $-3,221.57 | 0.0040 |
| mid_weak | 13 | -0.015487 | $-247.80 | $-437.32 | -0.3270 | $-3,221.35 | 0.0072 |
| late_strong | 13 | 0.00019 | $3.04 | $48.99 | 0.0259 | $39.46 | 0.0002 |

- Aggregate EV delta: `-0.487`
- Aggregate PnL delta: `$-6,403.46`
- DSR: `not_computable` / probability `None`
- Failed checks: `all_window_ev_nonnegative, all_window_pnl_nonnegative, all_window_cash_replacement_positive, all_window_qqq_replacement_positive, aggregate_ev_beats_accepted_comparator, aggregate_pnl_beats_accepted_comparator, drawdown_passed, dsr_passed, top_tenor_concentration_passed, top5_trade_concentration_passed`

## Boundary

Do not retune the bid-to-cover threshold, lookback, tenor subset, same-day attribution, TBT/short-TLT proxy, entry timing, hold, cost, overlap, or notional on these frozen auction rows.

No JavaScript was used.
