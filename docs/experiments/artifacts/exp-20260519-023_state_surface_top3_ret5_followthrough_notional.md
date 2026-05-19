# exp-20260519-023 State-Surface Top-3 Ret5 Follow-Through Notional

Decision: `accepted_default_off_state_surface_top3_ret5_followthrough_notional`.

Single causal variable: `top3_ret5_followthrough_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Ret5 Min | Scalar | Max Queue Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank2_volume_confirmation_notional | FAIL | n/a | n/a | 3 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 42.91% |
| top3_ret5_gt_0_scalar_110 | PASS | 0.0 | 1.1 | 3 | +0.2901 | $+5,643.32 | 3 | 0 | 18 | +0.1800% | 41.82% |
| top3_ret5_gt_0_scalar_125 | PASS | 0.0 | 1.25 | 3 | +0.7211 | $+14,108.30 | 3 | 0 | 18 | +0.4400% | 40.43% |
| top3_ret5_gt_0_scalar_150 | FAIL | 0.0 | 1.5 | 3 | +1.4452 | $+28,216.59 | 3 | 0 | 18 | +0.8700% | 38.63% |
| top3_ret5_gt_005_scalar_110 | PASS | 0.05 | 1.1 | 3 | +0.1351 | $+2,434.14 | 3 | 0 | 12 | +0.1600% | 41.56% |
| top3_ret5_gt_005_scalar_125 | PASS | 0.05 | 1.25 | 3 | +0.3556 | $+6,085.36 | 3 | 0 | 12 | +0.4000% | 39.68% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.2688 | 6.5002 | +0.2314 | $135,104.26 | $138,892.95 | $+3,788.69 | 6.95% | 7.35% | 6 |
| mid_weak | 4.3551 | 4.6833 | +0.3282 | $114,007.94 | $118,563.49 | $+4,555.55 | 10.57% | 10.43% | 9 |
| old_thin | 1.2357 | 1.3972 | +0.1615 | $62,724.22 | $68,488.28 | $+5,764.06 | 8.91% | 9.35% | 3 |

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
