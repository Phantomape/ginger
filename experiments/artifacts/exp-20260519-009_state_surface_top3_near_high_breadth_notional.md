# exp-20260519-009 State-Surface Top-3 Near-High Breadth Notional

Decision: `rejected_state_surface_top3_near_high_breadth_notional`.

Single causal variable: `top3_near_high_breadth_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Near High Min | Min Count | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank3_near_high_support_notional | FAIL | n/a | n/a | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 38.43% |
| top3_near_high_count2_ge_0975_balanced | FAIL | 0.975 | 2 | [1.8, 1.55, 1.25, 0.675, 0.35] | -0.2510 | $-3,063.09 | 1 | 2 | 15 | +0.0000% | 37.21% |
| top3_near_high_count2_ge_0975_rank1_heavy | FAIL | 0.975 | 2 | [2.0, 1.45, 1.15, 0.675, 0.35] | -0.2177 | $-2,555.23 | 1 | 2 | 15 | +0.0000% | 35.42% |
| top3_near_high_count2_ge_098_balanced | FAIL | 0.98 | 2 | [1.8, 1.55, 1.25, 0.675, 0.35] | -0.0449 | $-304.77 | 1 | 2 | 9 | +0.0000% | 37.22% |
| top3_near_high_count3_ge_0975_balanced | FAIL | 0.975 | 3 | [1.8, 1.55, 1.25, 0.675, 0.35] | +0.0013 | $+70.37 | 1 | 0 | 3 | +0.0000% | 37.04% |
| top3_near_high_count2_ge_0970_conservative | FAIL | 0.97 | 2 | [1.7, 1.45, 1.2, 0.675, 0.35] | -0.3094 | $-4,816.02 | 0 | 3 | 15 | +0.0500% | 37.09% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0760 | 6.0760 | +0.0000 | $131,800.12 | $131,800.12 | $+0.00 | 6.92% | 6.92% | 0 |
| mid_weak | 3.9848 | 3.9848 | +0.0000 | $108,578.34 | $108,578.34 | $+0.00 | 10.63% | 10.63% | 0 |
| old_thin | 1.0409 | 1.0422 | +0.0013 | $55,664.17 | $55,734.54 | $+70.37 | 9.06% | 9.05% | 3 |

## Interpretation

Top-3 near-high breadth did not meet the harder tail-aware gate. Treat the result as attribution only, not another shared notional rule.

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
