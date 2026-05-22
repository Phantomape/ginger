# exp-20260522-003 Broad-Market Red-Day Pullback Notional

Decision: `blocked_broad_market_red_day_pullback_identity_drift`.

Single causal variable: default-off paper notional scalar for already-selected broad-market candidates with decision-day 1-day return below zero.

## Sweep

| Variant | Gate 4 | Target | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_red_day_pullback_scalar | FAIL | 19 | +0.2886 | $+1,277.48 | 2 | 1 | +1.9300% | 11.77% | 42.37% |
| red_day_scalar_0p50 | FAIL | 19 | +0.4450 | $+1,759.53 | 2 | 1 | +1.9500% | 12.32% | 44.37% |
| red_day_scalar_0p75 | FAIL | 19 | +0.3705 | $+1,518.52 | 2 | 1 | +1.9400% | 12.04% | 43.34% |
| red_day_scalar_0p90 | FAIL | 19 | +0.3081 | $+1,373.87 | 2 | 1 | +1.9300% | 11.87% | 42.75% |
| red_day_scalar_1p05 | FAIL | 19 | +0.2707 | $+1,229.27 | 2 | 1 | +1.9300% | 11.71% | 42.18% |
| red_day_scalar_1p10 | FAIL | 19 | +0.2440 | $+1,181.08 | 2 | 1 | +1.9200% | 11.66% | 41.99% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.6537 | +0.2347 | $159,891.81 | $164,242.79 | $+4,350.98 |
| mid_weak | 7.3451 | 7.7800 | +0.4349 | $160,023.22 | $164,482.95 | $+4,459.73 |
| old_thin | 2.0757 | 1.8511 | -0.2246 | $94,782.99 | $87,731.81 | $-7,051.18 |

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
