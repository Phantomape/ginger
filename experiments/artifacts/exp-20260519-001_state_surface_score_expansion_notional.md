# exp-20260519-001 State-Surface Score-Expansion Notional

Decision: `accepted_default_off_state_surface_score_expansion_notional`.

Single causal variable: `residual_score_expansion_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Spread | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank1_ret60_residual_notional | FAIL | n/a | None | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 38.01% |
| residual_score_expansion_ge_040_rank1_top | PASS | 0.40 | [1.85, 1.25, 1.0, 0.675, 0.35] | +0.0552 | $+725.33 | 2 | 0 | 6 | +0.1400% | 37.43% |
| residual_score_expansion_ge_040_balanced_top2 | FAIL | 0.40 | [1.55, 1.55, 1.0, 0.675, 0.35] | -0.0394 | $-634.40 | 0 | 2 | 6 | +0.0000% | 38.35% |
| residual_score_expansion_ge_080_rank1_top | FAIL | 0.80 | [1.85, 1.25, 1.0, 0.675, 0.35] | +0.0408 | $+609.34 | 1 | 0 | 3 | +0.1400% | 37.62% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8815 | 5.9223 | +0.0408 | $128,980.91 | $129,590.25 | $+609.34 | 6.53% | 6.67% | 3 |
| mid_weak | 3.6468 | 3.6612 | +0.0144 | $103,307.84 | $103,423.83 | $+115.99 | 10.63% | 10.63% | 3 |
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
