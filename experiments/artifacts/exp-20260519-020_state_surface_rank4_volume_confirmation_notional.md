# exp-20260519-020 State-Surface Rank-4 Volume Confirmation Notional

Decision: `rejected_state_surface_rank4_volume_confirmation_notional`.

Single causal variable: `rank4_volume_confirmation_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Volume Min | Scalar | Target Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank3_volume_confirmation_notional | FAIL | n/a | n/a | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_100_scalar_125 | FAIL | 1.0 | 1.25 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_100_scalar_150 | FAIL | 1.0 | 1.5 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_110_scalar_125 | FAIL | 1.1 | 1.25 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_110_scalar_150 | FAIL | 1.1 | 1.5 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_120_scalar_125 | FAIL | 1.2 | 1.25 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_120_scalar_150 | FAIL | 1.2 | 1.5 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_130_scalar_125 | FAIL | 1.3 | 1.25 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| rank4_volume_ge_130_scalar_150 | FAIL | 1.3 | 1.5 | 4 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.2506 | 6.2506 | +0.0000 | $134,711.56 | $134,711.56 | $+0.00 | 6.94% | 6.94% | 0 |
| mid_weak | 4.2559 | 4.2559 | +0.0000 | $112,590.97 | $112,590.97 | $+0.00 | 10.62% | 10.62% | 0 |
| old_thin | 1.1932 | 1.1932 | +0.0000 | $61,187.32 | $61,187.32 | $+0.00 | 8.77% | 8.77% | 0 |

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
