# exp-20260520-005 Broad-Market Strong-Close Crowding Haircut

Decision: `rejected_broad_market_strong_close_crowding_haircut`.

Single causal variable: decision-day close-location paper-notional haircut on the fixed exp-20260520-004 broad-market paper sleeve.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_strong_close_crowding | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 13.52% | 42.72% |
| close_loc_gte_0p75_scalar_0p85 | FAIL | 42 | -0.0489 | $-2,346.58 | 1 | 2 | +0.2000% | 14.69% | 42.84% |
| close_loc_gte_0p75_scalar_0p90 | FAIL | 42 | -0.0357 | $-1,564.40 | 1 | 2 | +0.1300% | 14.28% | 42.80% |
| close_loc_gte_0p75_scalar_0p95 | FAIL | 42 | -0.0227 | $-782.22 | 1 | 2 | +0.0700% | 13.89% | 42.76% |
| close_loc_gte_0p80_scalar_0p85 | FAIL | 36 | -0.0438 | $-2,069.52 | 1 | 2 | +0.2000% | 14.61% | 42.61% |
| close_loc_gte_0p80_scalar_0p90 | FAIL | 36 | -0.0323 | $-1,379.69 | 1 | 2 | +0.1300% | 14.23% | 42.65% |
| close_loc_gte_0p80_scalar_0p95 | FAIL | 36 | -0.0209 | $-689.86 | 1 | 2 | +0.0700% | 13.87% | 42.68% |
| close_loc_gte_0p85_scalar_0p85 | FAIL | 25 | +0.0397 | $-8.89 | 3 | 0 | +0.0200% | 13.92% | 43.45% |
| close_loc_gte_0p85_scalar_0p90 | FAIL | 25 | +0.0424 | $-5.93 | 3 | 0 | +0.0200% | 13.79% | 43.20% |
| close_loc_gte_0p85_scalar_0p95 | FAIL | 25 | +0.0132 | $-2.98 | 3 | 0 | +0.0100% | 13.65% | 42.96% |
| close_loc_gte_0p90_scalar_0p85 | FAIL | 14 | +0.0177 | $-201.91 | 3 | 0 | +0.0000% | 13.73% | 42.86% |
| close_loc_gte_0p90_scalar_0p90 | FAIL | 14 | +0.0065 | $-134.60 | 2 | 1 | +0.0000% | 13.66% | 42.81% |
| close_loc_gte_0p90_scalar_0p95 | FAIL | 14 | +0.0112 | $-67.31 | 3 | 0 | +0.0000% | 13.59% | 42.76% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4378 | +0.0188 | $159,891.81 | $159,610.23 | $-281.58 |
| mid_weak | 7.3451 | 7.3640 | +0.0189 | $160,023.22 | $160,087.64 | $+64.42 |
| old_thin | 2.0757 | 2.0804 | +0.0047 | $94,782.99 | $94,994.22 | $+211.23 |

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
