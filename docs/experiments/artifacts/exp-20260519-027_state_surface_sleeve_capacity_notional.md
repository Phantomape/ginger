# exp-20260519-027 State-Surface Sleeve Capacity Notional

Decision: `accepted_default_off_state_surface_sleeve_capacity_notional`.

Single causal variable: `sleeve_capacity_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank_queue_alignment_notional | FAIL | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.74% |
| sleeve_capacity_scalar_103 | PASS | 1.03 | +0.1896 | $+3,242.22 | 3 | 0 | 24 | +0.0800% | 41.74% |
| sleeve_capacity_scalar_105 | PASS | 1.05 | +0.2935 | $+5,403.71 | 3 | 0 | 24 | +0.1400% | 41.74% |
| sleeve_capacity_scalar_108 | PASS | 1.08 | +0.4723 | $+8,645.94 | 3 | 0 | 24 | +0.2200% | 41.74% |
| sleeve_capacity_scalar_110 | PASS | 1.1 | +0.5853 | $+10,807.42 | 3 | 0 | 24 | +0.2700% | 41.74% |
| sleeve_capacity_scalar_115 | PASS | 1.15 | +0.8724 | $+16,211.14 | 3 | 0 | 24 | +0.4100% | 41.74% |
| sleeve_capacity_scalar_120 | FAIL | 1.2 | +1.1626 | $+21,614.84 | 3 | 0 | 24 | +0.5400% | 41.74% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.5949 | 6.7954 | +0.2005 | $140,316.57 | $143,665.49 | $+3,348.92 | 7.65% | 8.00% | 9 |
| mid_weak | 5.3028 | 5.8262 | +0.5234 | $127,472.12 | $134,865.68 | $+7,393.56 | 10.25% | 10.12% | 12 |
| old_thin | 1.6139 | 1.7624 | +0.1485 | $76,125.66 | $81,594.32 | $+5,468.66 | 9.92% | 10.33% | 3 |

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
