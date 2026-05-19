# exp-20260519-034 Broad-Market Leadership Candidate-Pool Shadow

Decision: `rejected_broad_market_leadership_candidate_pool_shadow`.

Single causal variable: default-off broad-market leadership candidate-pool membership from the exp-20260519-030 OHLCV warehouse.

## Sweep

| Variant | Gate 4 | Trades | Tickers | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| leadership_strict | FAIL | 90 | 76 | +1.1046 | $+23,382.05 | 2 | 1 | +0.7000% | 12.20% | 43.60% |
| leadership_balanced | FAIL | 90 | 71 | +0.2950 | $+18,751.18 | 2 | 1 | +0.3300% | 12.08% | 48.03% |
| leadership_broad | FAIL | 90 | 71 | +1.0062 | $+33,789.13 | 2 | 1 | +0.2800% | 10.75% | 45.78% |

## Selected Profile

Selected variant: `leadership_strict`.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Broad Trades | Broad PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1202 | 6.3506 | -0.7696 | $149,584.06 | $144,989.88 | $-4,594.18 | 30 | $-4,594.19 |
| mid_weak | 6.5001 | 8.2155 | +1.7154 | $145,415.33 | $168,350.82 | $+22,935.49 | 30 | $+22,935.47 |
| old_thin | 1.9959 | 2.1547 | +0.1588 | $90,723.08 | $95,763.82 | $+5,040.74 | 30 | $+5,040.75 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_order_path_changed": false,
  "note": "No core production behavior changed. A positive result is only a research lead until implemented through a shared default-off paper adapter visible to both backtest and production.",
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
