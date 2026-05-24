# exp-20260524-024 Broad-Market Short-Horizon Return-Path Cluster

Decision: `rejected_broad_market_short_horizon_path_cluster`.

Single causal variable: `short_horizon_return_path_cluster` support scalar on the accepted broad-market paper sleeve.

## Sweep

| Variant | Cluster | Gate 4 | Adjusted | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |
|---|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_short_horizon_cluster_support | none | FAIL | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% |
| steady_continuation_scalar_1p025 | steady_continuation | FAIL | 46 | +0.0406 | +0.24% | $+565.02 | 3 | 0 | +0.0100% |
| steady_continuation_scalar_1p05 | steady_continuation | FAIL | 46 | +0.0651 | +0.39% | $+1,129.90 | 3 | 0 | +0.0100% |
| steady_continuation_scalar_1p075 | steady_continuation | FAIL | 46 | +0.0897 | +0.53% | $+1,694.77 | 3 | 0 | +0.0200% |
| steady_continuation_scalar_1p1 | steady_continuation | FAIL | 46 | +0.1304 | +0.77% | $+2,259.82 | 3 | 0 | +0.0300% |
| steady_continuation_scalar_1p15 | steady_continuation | FAIL | 46 | +0.1797 | +1.07% | $+3,389.72 | 3 | 0 | +0.0500% |
| orderly_pullback_scalar_1p025 | orderly_pullback | FAIL | 2 | -0.0164 | -0.10% | $-8.26 | 1 | 1 | +0.0000% |
| orderly_pullback_scalar_1p05 | orderly_pullback | FAIL | 2 | -0.0169 | -0.10% | $-16.52 | 1 | 1 | +0.0000% |
| orderly_pullback_scalar_1p075 | orderly_pullback | FAIL | 2 | -0.0173 | -0.10% | $-24.79 | 1 | 1 | +0.0000% |
| orderly_pullback_scalar_1p1 | orderly_pullback | FAIL | 2 | -0.0178 | -0.11% | $-33.06 | 1 | 1 | +0.0000% |
| orderly_pullback_scalar_1p15 | orderly_pullback | FAIL | 2 | -0.0186 | -0.11% | $-49.58 | 1 | 1 | +0.0100% |
| constructive_chop_scalar_1p025 | constructive_chop | FAIL | 11 | +0.0000 | +0.00% | $+6.30 | 2 | 1 | +0.0000% |
| constructive_chop_scalar_1p05 | constructive_chop | FAIL | 11 | -0.0096 | -0.06% | $+12.56 | 1 | 2 | +0.0100% |
| constructive_chop_scalar_1p075 | constructive_chop | FAIL | 11 | -0.0096 | -0.06% | $+18.84 | 1 | 2 | +0.0100% |
| constructive_chop_scalar_1p1 | constructive_chop | FAIL | 11 | -0.0095 | -0.06% | $+25.12 | 1 | 2 | +0.0100% |
| constructive_chop_scalar_1p15 | constructive_chop | FAIL | 11 | -0.0095 | -0.06% | $+37.69 | 1 | 2 | +0.0200% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4819 | +0.0629 | $159,891.81 | $160,900.49 | $+1,008.68 |
| mid_weak | 7.3451 | 7.4539 | +0.1088 | $160,023.22 | $162,040.50 | $+2,017.28 |
| old_thin | 2.0757 | 2.0837 | +0.0080 | $94,782.99 | $95,146.75 | $+363.76 |

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_order_path_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
