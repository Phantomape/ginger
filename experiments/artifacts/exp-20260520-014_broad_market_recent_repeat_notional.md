# exp-20260520-014 Broad-Market Recent-Repeat Notional

Decision: `rejected_broad_market_recent_repeat_notional`.

Single causal variable: notional scalar for already-selected broad-market candidates whose ticker was selected again within the prior 60 calendar days.

## Sweep

| Variant | Gate 4 | Targeted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Target Single | Target Top5 |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_recent_repeat_scalar | FAIL | 3 | +0.2886 | $+1,277.48 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_0p50 | FAIL | 3 | +0.6008 | $+3,713.92 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_0p75 | FAIL | 3 | +0.4279 | $+2,495.69 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_0p90 | FAIL | 3 | +0.3442 | $+1,764.76 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_1p10 | FAIL | 3 | +0.2166 | $+790.18 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_1p15 | FAIL | 3 | +0.1889 | $+546.54 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_1p25 | FAIL | 3 | +0.1335 | $+59.25 | 2 | 1 | +1.9300% | 100.00% | 100.00% |
| recent_repeat_scalar_1p50 | FAIL | 3 | -0.0210 | $-1,158.97 | 2 | 1 | +1.9300% | 100.00% | 100.00% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.8633 | +0.4443 | $159,891.81 | $165,542.40 | $+5,650.59 |
| mid_weak | 7.3451 | 7.7584 | +0.4133 | $160,023.22 | $165,423.95 | $+5,400.73 |
| old_thin | 2.0757 | 1.8189 | -0.2568 | $94,782.99 | $87,445.59 | $-7,337.40 |

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
