# exp-20260519-035 Broad-Market Price-Floor Candidate-Pool Shadow

Decision: `observed_promising_default_off_broad_market_price_floor_candidate_pool`.

Single causal variable: decision-date close price floor on the exp-20260519-034 broad-market leadership parent pool.

## Sweep

| Variant | Gate 4 | Trades | Tickers | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| price_floor_30 | FAIL | 90 | 71 | +1.1191 | $+27,686.16 | 2 | 1 | +0.6700% | 11.79% | 42.13% |
| price_floor_35 | FAIL | 90 | 72 | +1.1634 | $+26,977.12 | 2 | 1 | +0.6700% | 12.34% | 41.56% |
| price_floor_40 | PASS | 90 | 68 | +0.7208 | $+18,639.46 | 3 | 0 | +0.2300% | 11.16% | 39.42% |
| price_floor_45 | PASS | 90 | 67 | +0.6621 | $+18,038.32 | 3 | 0 | +0.2300% | 11.38% | 40.20% |
| price_floor_50 | FAIL | 90 | 70 | +0.7767 | $+18,942.67 | 2 | 1 | +0.6900% | 11.13% | 41.92% |

## Selected Profile

Selected variant: `price_floor_40`.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Broad Trades | Broad PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1202 | 7.1323 | +0.0121 | $149,584.06 | $154,379.70 | $+4,795.64 | 30 | $+4,795.63 |
| mid_weak | 6.5001 | 7.1660 | +0.6659 | $145,415.33 | $156,462.94 | $+11,047.61 | 30 | $+11,047.57 |
| old_thin | 1.9959 | 2.0387 | +0.0428 | $90,723.08 | $93,519.29 | $+2,796.21 | 30 | $+2,796.22 |

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
