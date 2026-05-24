# exp-20260524-023 Broad-Market Correlation Crowding Replacement

Decision: `rejected_broad_market_correlation_crowding`.

Single causal variable: trailing-20-day positive return correlation cap against already-open or same-day selected broad-market sleeve names.

## Sweep

| Variant | Gate 4 | Replaced | Blocked | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_correlation_cap | FAIL | 0 | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% | 42.72% |
| corr_cap_0p95 | FAIL | 0 | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% | 42.72% |
| corr_cap_0p90 | FAIL | 4 | 2 | +0.4350 | +2.58% | $+4,921.44 | 2 | 0 | +0.0000% | 42.69% |
| corr_cap_0p85 | FAIL | 5 | 4 | +0.4375 | +2.60% | $+5,035.10 | 2 | 0 | +0.0000% | 42.44% |
| corr_cap_0p80 | FAIL | 7 | 8 | +0.5117 | +3.04% | $+5,880.58 | 3 | 0 | -0.0300% | 42.43% |
| corr_cap_0p75 | FAIL | 9 | 10 | +0.5619 | +3.34% | $+7,166.44 | 3 | 0 | -0.0300% | 42.32% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4767 | +0.0577 | $159,891.81 | $160,443.93 | $+552.12 |
| mid_weak | 7.3451 | 7.6228 | +0.2777 | $160,023.22 | $162,187.57 | $+2,164.35 |
| old_thin | 2.0757 | 2.3022 | +0.2265 | $94,782.99 | $99,232.96 | $+4,449.97 |

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
