# exp-20260519-025 State-Surface Rank-1 Dominance Crowding Penalty

Decision: `rejected_state_surface_rank1_dominance_crowding_penalty_notional`.

Single causal variable: `rank1_dominance_crowding_penalty_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Lead Min | Gap Min | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_broad_breadth_support_notional | FAIL | n/a | n/a | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.30% |
| rank1_dominance_crowding_scalar_095 | FAIL | 0.15 | 0.45 | 0.95 | +0.0098 | $-43.70 | 1 | 1 | 2 | +0.0000% | 41.35% |
| rank1_dominance_crowding_scalar_090 | FAIL | 0.15 | 0.45 | 0.9 | +0.0073 | $-87.39 | 1 | 1 | 2 | +0.0000% | 41.39% |
| rank1_dominance_crowding_scalar_085 | FAIL | 0.15 | 0.45 | 0.85 | +0.0171 | $-131.10 | 1 | 1 | 2 | +0.0000% | 41.43% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.5002 | 6.4843 | -0.0159 | $138,892.95 | $138,553.51 | $-339.44 | 7.35% | 7.35% | 1 |
| mid_weak | 4.9531 | 4.9861 | +0.0330 | $122,601.66 | $122,810.00 | $+208.34 | 10.36% | 10.36% | 1 |
| old_thin | 1.4845 | 1.4845 | +0.0000 | $71,370.31 | $71,370.31 | $+0.00 | 9.56% | 9.56% | 0 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
