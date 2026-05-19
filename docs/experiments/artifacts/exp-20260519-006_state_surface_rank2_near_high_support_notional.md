# exp-20260519-006 State-Surface Rank-2 Near-High Support Notional

Decision: `accepted_default_off_state_surface_rank2_near_high_support_notional`.

Single causal variable: `rank2_near_high_support_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Near High Min | Scalar | Target Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank3_near_high_support_notional | FAIL | n/a | n/a | 2 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 38.43% |
| rank2_near_high_ge_098_scalar_125 | FAIL | 0.98 | 1.25 | 2 | +0.0278 | $+508.62 | 1 | 1 | 2 | +0.0000% | 38.01% |
| rank2_near_high_ge_098_scalar_150 | FAIL | 0.98 | 1.5 | 2 | +0.0532 | $+1,017.23 | 1 | 1 | 2 | +0.0000% | 37.60% |
| rank2_near_high_ge_0975_scalar_125 | PASS | 0.975 | 1.25 | 2 | +0.1833 | $+4,191.04 | 3 | 0 | 5 | +0.0100% | 41.26% |
| rank2_near_high_ge_0975_scalar_150 | PASS | 0.975 | 1.5 | 2 | +0.3390 | $+8,382.06 | 3 | 0 | 5 | +0.0200% | 43.75% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0760 | 6.1501 | +0.0741 | $131,800.12 | $133,119.67 | $+1,319.55 | 6.92% | 6.94% | 2 |
| mid_weak | 3.9848 | 4.1113 | +0.1265 | $108,578.34 | $110,517.86 | $+1,939.52 | 10.63% | 10.63% | 2 |
| old_thin | 1.0409 | 1.1793 | +0.1384 | $55,664.17 | $60,787.16 | $+5,122.99 | 9.06% | 8.79% | 1 |

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
