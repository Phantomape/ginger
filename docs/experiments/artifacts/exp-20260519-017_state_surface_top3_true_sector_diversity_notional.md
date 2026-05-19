# exp-20260519-017 State-Surface Top-3 Sector Diversity Notional

Decision: `rejected_state_surface_top3_sector_diversity_notional`.

Single causal variable: `top3_sector_diversity_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank3_volume_confirmation_notional | FAIL | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.52% |
| top3_sector_diversity_rank1_lift | FAIL | [1.75, 1.3, 1.0, 0.675, 0.35] | -0.5078 | $-6,727.60 | 0 | 2 | 18 | +0.0700% | 41.88% |
| top3_sector_diversity_rank2_lift | FAIL | [1.45, 1.65, 1.05, 0.675, 0.35] | -0.4070 | $-5,274.76 | 0 | 2 | 18 | +0.0100% | 43.06% |
| top3_sector_diversity_rank3_lift | FAIL | [1.45, 1.25, 1.35, 0.675, 0.35] | -0.4918 | $-6,705.57 | 0 | 2 | 18 | +0.0900% | 42.16% |
| top3_sector_diversity_balanced | FAIL | [1.6, 1.4, 1.15, 0.675, 0.35] | -0.4554 | $-5,949.62 | 0 | 2 | 18 | +0.0500% | 42.11% |
| top3_sector_diversity_depth_relief | FAIL | [1.35, 1.45, 1.3, 0.675, 0.35] | -0.4466 | $-5,942.58 | 0 | 2 | 18 | +0.0500% | 42.76% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.2506 | 6.0096 | -0.2410 | $134,711.56 | $131,789.02 | $-2,922.54 | 6.94% | 6.41% | 9 |
| mid_weak | 4.2559 | 4.0899 | -0.1660 | $112,590.97 | $110,238.75 | $-2,352.22 | 10.62% | 10.63% | 9 |
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
