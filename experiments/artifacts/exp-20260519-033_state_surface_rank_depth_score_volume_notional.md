# exp-20260519-033 State-Surface Rank-Depth Score-Volume Notional

Decision: `accepted_default_off_state_surface_rank_depth_score_volume_notional`.

Single causal variable: `rank_depth_score_volume_notional_scalar` for already-selected default-off state-surface paper candidates.

## Sweep

| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_absolute_score_support_notional | FAIL | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 42.36% |
| rank_depth_score_volume_scalar_1p025 | PASS | 1.025 | +0.0582 | $+1,454.51 | 3 | 0 | 7 | +0.1600% | 42.80% |
| rank_depth_score_volume_scalar_1p05 | PASS | 1.05 | +0.1019 | $+2,909.00 | 3 | 0 | 7 | +0.3100% | 43.24% |
| rank_depth_score_volume_scalar_1p075 | PASS | 1.075 | +0.1602 | $+4,363.51 | 3 | 0 | 7 | +0.4700% | 43.67% |
| rank_depth_score_volume_scalar_1p1 | FAIL | 1.1 | +0.2039 | $+5,818.01 | 3 | 0 | 7 | +0.6300% | 44.09% |
| rank_depth_score_volume_scalar_1p125 | FAIL | 1.125 | +0.2624 | $+7,272.50 | 3 | 0 | 7 | +0.7900% | 44.50% |
| rank_depth_score_volume_scalar_1p15 | FAIL | 1.15 | +0.3062 | $+8,727.00 | 3 | 0 | 7 | +0.9400% | 44.91% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1075 | 7.1202 | +0.0127 | $149,317.03 | $149,584.06 | $+267.03 | 8.38% | 8.39% | 3 |
| mid_weak | 6.4151 | 6.5001 | +0.0850 | $144,158.66 | $145,415.33 | $+1,256.67 | 10.10% | 10.10% | 2 |
| old_thin | 1.9334 | 1.9959 | +0.0625 | $87,883.27 | $90,723.08 | $+2,839.81 | 10.79% | 11.26% | 2 |

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
