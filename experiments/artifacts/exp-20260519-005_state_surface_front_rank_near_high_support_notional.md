# exp-20260519-005 State-Surface Front-Rank Near-High Support Notional

Decision: `rejected_state_surface_front_rank_near_high_support_notional`.

Single causal variable: `front_rank_near_high_support_notional_scalar` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Near High Min | Scalar | Max Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank3_near_high_support_notional | FAIL | n/a | n/a | 2 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 38.43% |
| front_rank_near_high_ge_098_scalar_110 | FAIL | 0.98 | 1.1 | 2 | +0.0780 | $+1,270.42 | 2 | 1 | 5 | +0.1700% | 37.59% |
| front_rank_near_high_ge_098_scalar_125 | FAIL | 0.98 | 1.25 | 2 | +0.1609 | $+3,176.04 | 2 | 1 | 5 | +0.4100% | 36.40% |
| front_rank_near_high_ge_098_scalar_150 | FAIL | 0.98 | 1.5 | 2 | +0.3346 | $+6,352.09 | 2 | 1 | 5 | +0.8000% | 34.58% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0760 | 6.3551 | +0.2791 | $131,800.12 | $136,082.49 | $+4,282.37 | 6.92% | 7.72% | 3 |
| mid_weak | 3.9848 | 3.9591 | -0.0257 | $108,578.34 | $108,173.11 | $-405.23 | 10.63% | 10.63% | 1 |
| old_thin | 1.0409 | 1.1221 | +0.0812 | $55,664.17 | $58,139.12 | $+2,474.95 | 9.06% | 8.93% | 1 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
