# exp-20260519-021 State-Surface Rank-2 Volume Confirmation Notional

Decision: `accepted_default_off_state_surface_rank2_volume_confirmation_notional`.

Single causal variable: `rank2_volume_confirmation_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Volume Min | Scalar | Target Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank3_volume_confirmation_notional | FAIL | n/a | n/a | 2 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank2_volume_ge_100_scalar_110 | PASS | 1.0 | 1.1 | 2 | +0.1599 | $+3,346.57 | 3 | 0 | 7 | +0.1400% | 42.91% |
| rank2_volume_ge_100_scalar_125 | FAIL | 1.0 | 1.25 | 2 | +0.3966 | $+8,366.44 | 3 | 0 | 7 | +0.6200% | 44.78% |
| rank2_volume_ge_100_scalar_150 | FAIL | 1.0 | 1.5 | 2 | +0.7843 | $+16,732.87 | 3 | 0 | 7 | +1.4100% | 47.44% |
| rank2_volume_ge_110_scalar_110 | PASS | 1.1 | 1.1 | 2 | +0.1599 | $+3,346.57 | 3 | 0 | 7 | +0.1400% | 42.91% |
| rank2_volume_ge_110_scalar_125 | FAIL | 1.1 | 1.25 | 2 | +0.3966 | $+8,366.44 | 3 | 0 | 7 | +0.6200% | 44.78% |
| rank2_volume_ge_110_scalar_150 | FAIL | 1.1 | 1.5 | 2 | +0.7843 | $+16,732.87 | 3 | 0 | 7 | +1.4100% | 47.44% |
| rank2_volume_ge_120_scalar_125 | FAIL | 1.2 | 1.25 | 2 | +0.2993 | $+4,601.37 | 2 | 0 | 5 | +0.0000% | 42.27% |
| rank2_volume_ge_120_scalar_150 | FAIL | 1.2 | 1.5 | 2 | +0.6072 | $+9,202.74 | 2 | 0 | 5 | +0.0000% | 42.94% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.2506 | 6.2688 | +0.0182 | $134,711.56 | $135,104.26 | $+392.70 | 6.94% | 6.95% | 3 |
| mid_weak | 4.2559 | 4.3551 | +0.0992 | $112,590.97 | $114,007.94 | $+1,416.97 | 10.62% | 10.57% | 3 |
| old_thin | 1.1932 | 1.2357 | +0.0425 | $61,187.32 | $62,724.22 | $+1,536.90 | 8.77% | 8.91% | 1 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": true,
  "replay_only": true,
  "run_adapter_changed": true,
  "shared_policy_changed": true
}
```

No JavaScript was used.
