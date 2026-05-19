# exp-20260518-025 State-Surface Top-2 Technology Cohesion Notional

Decision: `accepted_default_off_state_surface_top2_tech_cohesion_notional`.

Single causal variable: `top2_technology_sector_cohesion_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank1_ret20_dominance_notional | FAIL | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 36.55% |
| top2_tech_rank2_lift | PASS | [1.45, 1.7, 1.15, 0.675, 0.35] | +0.0759 | $+1,593.99 | 2 | 0 | 6 | +0.0000% | 36.80% |
| top2_tech_rank23_lift | PASS | [1.4, 1.7, 1.25, 0.675, 0.35] | +0.0728 | $+1,448.60 | 2 | 0 | 6 | +0.0000% | 36.89% |
| top2_tech_balanced | PASS | [1.55, 1.55, 1.1, 0.675, 0.35] | +0.0401 | $+742.50 | 2 | 0 | 6 | +0.0000% | 34.62% |
| top2_tech_rank2_heavy | PASS | [1.2, 1.9, 1.2, 0.675, 0.35] | +0.0746 | $+1,732.54 | 2 | 0 | 6 | +0.0000% | 40.29% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8667 | 5.8667 | +0.0000 | $128,938.31 | $128,938.31 | $+0.00 | 6.53% | 6.53% | 0 |
| mid_weak | 3.4879 | 3.5407 | +0.0528 | $100,805.09 | $101,743.76 | $+938.67 | 10.63% | 10.63% | 3 |
| old_thin | 1.0073 | 1.0304 | +0.0231 | $54,742.08 | $55,397.40 | $+655.32 | 9.11% | 9.07% | 3 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "live_default_orders_changed": false,
  "parity_test_added": true,
  "replay_only": true,
  "run_adapter_changed": true,
  "shared_policy_changed": true
}
```

No JavaScript was used.
