# exp-20260527-025 Broad-Market Idiosyncratic Residual Leadership

Decision: `rejected_broad_market_idiosyncratic_residual_leadership`.

Single causal variable: beta-adjusted 20-day idiosyncratic residual return substituted for raw SPY-relative 20-day momentum in the broad-market paper candidate surface.

## Sweep

| Variant | Gate 4 | Replaced | dEV | Rel EV | dPnL | EV Improved | EV Regressed | PnL Regressed | Max DD Worse | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_original_profile | FAIL | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | 0 | +0.0000% | 42.72% |
| residual_rank_original_profile | FAIL | 9 | -0.3504 | -2.08% | $-4,290.09 | 1 | 2 | 2 | +0.0900% | 44.25% |
| residual_profile_min_0p025 | FAIL | 9 | -0.3504 | -2.08% | $-4,290.09 | 1 | 2 | 2 | +0.0900% | 44.25% |
| residual_profile_min_0p035 | FAIL | 9 | -0.3504 | -2.08% | $-4,290.09 | 1 | 2 | 2 | +0.0900% | 44.25% |
| residual_profile_min_0p050 | FAIL | 9 | -0.3504 | -2.08% | $-4,290.09 | 1 | 2 | 2 | +0.0900% | 44.25% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.3283 | -0.0907 | $159,891.81 | $158,622.09 | $-1,269.72 |
| mid_weak | 7.3451 | 7.0564 | -0.2887 | $160,023.22 | $156,115.69 | $-3,907.53 |
| old_thin | 2.0757 | 2.1047 | +0.0290 | $94,782.99 | $95,670.15 | $+887.16 |

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
  "note": "No production behavior changed. Promotion would require the same beta-adjusted residual calculation in a shared default-off paper adapter and parity tests.",
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
