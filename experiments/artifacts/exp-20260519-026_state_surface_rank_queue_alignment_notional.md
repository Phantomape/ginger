# exp-20260519-026 State-Surface Rank/Queue Alignment Notional

Decision: `accepted_default_off_state_surface_rank_queue_alignment_notional`.

Single causal variable: `rank_queue_alignment_notional_profile`.

## Sweep

| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_broad_breadth_support_notional | FAIL | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.30% |
| rank_queue_alignment_scalar_105 | PASS | 1.05 | +0.1917 | $+3,683.15 | 3 | 0 | 14 | +0.1200% | 41.46% |
| rank_queue_alignment_scalar_110 | PASS | 1.1 | +0.3926 | $+7,366.29 | 3 | 0 | 14 | +0.2400% | 41.60% |
| rank_queue_alignment_scalar_115 | PASS | 1.15 | +0.5738 | $+11,049.43 | 3 | 0 | 14 | +0.3600% | 41.74% |
| rank_queue_alignment_scalar_125 | FAIL | 1.25 | +0.9552 | $+18,415.73 | 3 | 0 | 14 | +0.6000% | 41.99% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.5002 | 6.5949 | +0.0947 | $138,892.95 | $140,316.57 | $+1,423.62 | 7.35% | 7.65% | 5 |
| mid_weak | 4.9531 | 5.3028 | +0.3497 | $122,601.66 | $127,472.12 | $+4,870.46 | 10.36% | 10.25% | 6 |
| old_thin | 1.4845 | 1.6139 | +0.1294 | $71,370.31 | $76,125.66 | $+4,755.35 | 9.56% | 9.92% | 3 |

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
