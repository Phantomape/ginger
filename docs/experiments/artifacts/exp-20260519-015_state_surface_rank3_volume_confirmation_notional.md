# exp-20260519-015 State-Surface Rank-3 Volume Confirmation Notional

Decision: `accepted_default_off_state_surface_rank3_volume_confirmation_notional`.

Single causal variable: `rank3_volume_confirmation_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Volume Min | Scalar | Target Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank2_near_high_support_notional | FAIL | n/a | n/a | 3 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 43.75% |
| rank3_volume_ge_100_scalar_125 | PASS | 1.0 | 1.25 | 3 | +0.1300 | $+1,973.75 | 3 | 0 | 6 | +0.0000% | 42.61% |
| rank3_volume_ge_100_scalar_150 | PASS | 1.0 | 1.5 | 3 | +0.2433 | $+3,947.49 | 3 | 0 | 6 | +0.0000% | 41.52% |
| rank3_volume_ge_110_scalar_125 | PASS | 1.1 | 1.25 | 3 | +0.1322 | $+2,032.58 | 3 | 0 | 5 | +0.0000% | 42.61% |
| rank3_volume_ge_110_scalar_150 | PASS | 1.1 | 1.5 | 3 | +0.2590 | $+4,065.16 | 3 | 0 | 5 | +0.0000% | 41.52% |
| rank3_volume_ge_120_scalar_125 | PASS | 1.2 | 1.25 | 3 | +0.1322 | $+2,032.58 | 3 | 0 | 5 | +0.0000% | 42.61% |
| rank3_volume_ge_120_scalar_150 | PASS | 1.2 | 1.5 | 3 | +0.2590 | $+4,065.16 | 3 | 0 | 5 | +0.0000% | 41.52% |
| rank3_volume_ge_130_scalar_125 | FAIL | 1.3 | 1.25 | 3 | +0.0640 | $+1,098.39 | 3 | 0 | 4 | +0.0000% | 43.13% |
| rank3_volume_ge_130_scalar_150 | FAIL | 1.3 | 1.5 | 3 | +0.1220 | $+2,196.78 | 3 | 0 | 4 | +0.0000% | 42.52% |
| rank3_volume_ge_150_scalar_125 | FAIL | 1.5 | 1.25 | 3 | +0.0338 | $+735.17 | 3 | 0 | 3 | +0.0000% | 43.33% |
| rank3_volume_ge_150_scalar_150 | FAIL | 1.5 | 1.5 | 3 | +0.0615 | $+1,470.35 | 3 | 0 | 3 | +0.0000% | 42.92% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.1501 | 6.2506 | +0.1005 | $133,119.67 | $134,711.56 | $+1,591.89 | 6.94% | 6.94% | 2 |
| mid_weak | 4.1113 | 4.2559 | +0.1446 | $110,517.86 | $112,590.97 | $+2,073.11 | 10.63% | 10.62% | 2 |
| old_thin | 1.1793 | 1.1932 | +0.0139 | $60,787.16 | $61,187.32 | $+400.16 | 8.79% | 8.77% | 1 |

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
