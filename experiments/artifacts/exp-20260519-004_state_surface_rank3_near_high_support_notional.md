# exp-20260519-004 State-Surface Rank-3 Near-High Support Notional

Decision: `accepted_default_off_state_surface_rank3_near_high_support_notional`.

Single causal variable: `rank3_near_high_support_notional_scalar` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Near High Min | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank1_score_isolation_notional | FAIL | n/a | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 39.68% |
| rank3_near_high_ge_098_scalar_110 | PASS | 0.98 | 1.1 | +0.0149 | $+404.93 | 3 | 0 | 5 | +0.0000% | 39.42% |
| rank3_near_high_ge_098_scalar_125 | PASS | 0.98 | 1.25 | +0.0481 | $+1,012.31 | 3 | 0 | 5 | +0.0000% | 39.04% |
| rank3_near_high_ge_098_scalar_150 | PASS | 0.98 | 1.5 | +0.1126 | $+2,024.62 | 3 | 0 | 5 | +0.0000% | 38.43% |
| rank3_near_high_ge_099_scalar_125 | FAIL | 0.99 | 1.25 | +0.0013 | $+101.03 | 1 | 1 | 3 | +0.0000% | 39.59% |
| rank3_near_high_ge_099_scalar_150 | FAIL | 0.99 | 1.5 | -0.0026 | $+202.07 | 1 | 1 | 3 | +0.0000% | 39.50% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.0494 | 6.0760 | +0.0266 | $131,223.15 | $131,800.12 | $+576.97 | 6.92% | 6.92% | 1 |
| mid_weak | 3.9093 | 3.9848 | +0.0755 | $107,397.46 | $108,578.34 | $+1,180.88 | 10.63% | 10.63% | 3 |
| old_thin | 1.0304 | 1.0409 | +0.0105 | $55,397.40 | $55,664.17 | $+266.77 | 9.07% | 9.06% | 1 |

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
