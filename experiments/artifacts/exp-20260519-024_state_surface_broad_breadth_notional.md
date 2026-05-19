# exp-20260519-024 State-Surface Broad-Breadth Notional

Decision: `accepted_default_off_state_surface_broad_breadth_support_notional`.

Single causal variable: `broad_breadth_support_notional_profile` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Variant | Gate 4 | Breadth Bucket | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_top3_ret5_followthrough_notional | FAIL | n/a | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 40.43% |
| broad_breadth_scalar_105 | PASS | broad_breadth | 1.05 | +0.1833 | $+3,460.10 | 2 | 0 | 15 | +0.1100% | 40.88% |
| broad_breadth_scalar_110 | PASS | broad_breadth | 1.1 | +0.3571 | $+6,920.20 | 2 | 0 | 15 | +0.2100% | 41.30% |
| broad_breadth_scalar_125 | FAIL | broad_breadth | 1.25 | +0.9021 | $+17,300.52 | 2 | 0 | 15 | +0.5400% | 42.39% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.5002 | 6.5002 | +0.0000 | $138,892.95 | $138,892.95 | $+0.00 | 7.35% | 7.35% | 0 |
| mid_weak | 4.6833 | 4.9531 | +0.2698 | $118,563.49 | $122,601.66 | $+4,038.17 | 10.43% | 10.36% | 12 |
| old_thin | 1.3972 | 1.4845 | +0.0873 | $68,488.28 | $71,370.31 | $+2,882.03 | 9.35% | 9.56% | 3 |

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
