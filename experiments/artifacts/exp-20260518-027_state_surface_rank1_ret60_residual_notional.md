# exp-20260518-027 State-Surface Residual Rank-1 Ret60 Notional

Decision: `accepted_default_off_state_surface_rank1_ret60_residual_notional`.

Single causal variable: `rank1_ret60_residual_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Threshold | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_top2_tech_cohesion_notional | FAIL | n/a | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 36.80% |
| residual_rank1_ret60_ge_040_rank2_shift | FAIL | 0.40 | [1.2, 1.85, 1.1, 0.675, 0.35] | -0.0019 | $+31.63 | 1 | 1 | 9 | +0.0000% | 38.99% |
| residual_rank1_ret60_ge_050_rank2_shift | PASS | 0.50 | [1.2, 1.85, 1.1, 0.675, 0.35] | +0.1209 | $+1,606.68 | 2 | 0 | 6 | +0.0000% | 38.01% |
| residual_rank1_ret60_ge_060_mild_shift | PASS | 0.60 | [1.35, 1.65, 1.1, 0.675, 0.35] | +0.0758 | $+917.17 | 2 | 0 | 6 | +0.0000% | 37.48% |
| residual_rank1_ret60_ge_060_rank2_shift | PASS | 0.60 | [1.2, 1.85, 1.1, 0.675, 0.35] | +0.1209 | $+1,606.68 | 2 | 0 | 6 | +0.0000% | 38.01% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8667 | 5.8815 | +0.0148 | $128,938.31 | $128,980.91 | $+42.60 | 6.53% | 6.53% | 3 |
| mid_weak | 3.5407 | 3.6468 | +0.1061 | $101,743.76 | $103,307.84 | $+1,564.08 | 10.63% | 10.63% | 3 |
| old_thin | 1.0304 | 1.0304 | +0.0000 | $55,397.40 | $55,397.40 | $+0.00 | 9.07% | 9.07% | 0 |

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
