# exp-20260519-028 State-Surface Queue-Lag Support Notional

Decision: `accepted_default_off_state_surface_queue_lag_support_notional`.

Single causal variable: `queue_lag_support_notional_profile` for already-selected default-off state-surface paper candidates where `rank > queue_rank`.

## Sweep

| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_sleeve_capacity_notional | FAIL | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.74% |
| queue_lag_scalar_103 | PASS | 1.03 | +0.0499 | $+805.99 | 2 | 0 | 10 | +0.0000% | 41.65% |
| queue_lag_scalar_105 | PASS | 1.05 | +0.0742 | $+1,343.31 | 2 | 0 | 10 | +0.0000% | 41.59% |
| queue_lag_scalar_110 | PASS | 1.1 | +0.1487 | $+2,686.61 | 2 | 0 | 10 | +0.0000% | 41.45% |
| queue_lag_scalar_115 | PASS | 1.15 | +0.2378 | $+4,029.92 | 2 | 0 | 10 | +0.0000% | 41.30% |
| queue_lag_scalar_125 | PASS | 1.25 | +0.3875 | $+6,716.53 | 2 | 0 | 10 | +0.0000% | 41.03% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.7954 | 6.9653 | +0.1699 | $143,665.49 | $146,946.35 | $+3,280.86 | 8.00% | 8.00% | 4 |
| mid_weak | 5.8262 | 6.0438 | +0.2176 | $134,865.68 | $138,301.35 | $+3,435.67 | 10.12% | 10.12% | 6 |
| old_thin | 1.7624 | 1.7624 | +0.0000 | $81,594.32 | $81,594.32 | $+0.00 | 10.33% | 10.33% | 0 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": true,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true
}
```

No JavaScript was used.
