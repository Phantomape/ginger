# exp-20260519-010 SEC Earnings-Release Overlap Stack Cap

Decision: `rejected_sec_earnings_release_overlap_stack_cap`.

Single causal variable: `earnings_release_spy_context_neutral_underreaction_overlap_factor`.

## Sweep

| Variant | Gate | Factor | dEV | dPnL | EV+ Windows | EV- Windows | Trades | Max DD Worse | Single Share | Top5 | HHI |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_overlap_stack_factor_1_00 | FAIL | 1.00 | +0.1885 | $+5,461.48 | 3.0 | 0.0 | 29 | +0.1380% | 51.17% | 81.66% | 0.2907 |
| overlap_stack_factor_0_95 | FAIL | 0.95 | +0.1795 | $+5,228.30 | 2.0 | 1.0 | 29 | +0.1323% | 50.52% | 80.94% | 0.2842 |
| overlap_stack_factor_0_90 | FAIL | 0.90 | +0.1705 | $+4,995.12 | 2.0 | 1.0 | 29 | +0.1266% | 49.81% | 80.16% | 0.2774 |
| overlap_stack_factor_0_75 | FAIL | 0.75 | +0.1436 | $+4,295.60 | 2.0 | 1.0 | 29 | +0.1094% | 47.30% | 77.62% | 0.2541 |
| overlap_stack_factor_0_50 | FAIL | 0.50 | +0.0984 | $+3,129.71 | 2.0 | 1.0 | 29 | +0.0806% | 41.08% | 73.27% | 0.2039 |
| overlap_stack_factor_0_00 | FAIL | 0.00 | +0.0075 | $+797.94 | 2.0 | 1.0 | 29 | +0.0223% | 25.31% | 74.06% | 0.1420 |

## Three-Window Best Variant

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0011 | $+411.66 | +0.0000 |
| mid_weak | +0.1126 | $+1,784.32 | -0.0007 |
| old_thin | +0.0748 | $+3,265.50 | +0.0014 |

## Interpretation

No overlap stack factor preserved the earnings-release improvement while clearing the stricter tail-aware gate.

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
