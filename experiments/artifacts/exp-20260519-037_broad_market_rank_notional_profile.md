# exp-20260519-037 Broad-Market Rank-Notional Profile

Decision: `accepted_default_off_broad_market_rank_notional_profile`.

Single causal variable: rank-based paper notional multipliers on the fixed exp-20260519-036 broad-market leadership paper pool.

## Sweep

| Variant | Gate 4 | Trades | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flat_baseline | FAIL | 90 | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 11.16% | 39.42% |
| rank1_105_rank3_95 | PASS | 90 | +0.0585 | $+969.22 | 3 | 0 | +0.0400% | 11.45% | 40.28% |
| rank1_110_rank3_90 | PASS | 90 | +0.1171 | $+1,938.42 | 3 | 0 | +0.0800% | 11.72% | 41.10% |
| rank1_115_rank3_85 | PASS | 90 | +0.1758 | $+2,907.63 | 3 | 0 | +0.1100% | 11.99% | 41.88% |
| rank1_120_rank3_80 | PASS | 90 | +0.2189 | $+3,876.84 | 3 | 0 | +0.1500% | 12.24% | 42.63% |
| rank12_110_rank3_80 | PASS | 90 | +0.1016 | $+2,508.69 | 3 | 0 | +0.2300% | 11.51% | 40.66% |
| rank2_110_rank3_90 | FAIL | 90 | -0.0305 | $+570.26 | 2 | 1 | +0.1600% | 10.95% | 38.99% |
| rank2_115_rank3_85 | FAIL | 90 | -0.0332 | $+855.40 | 2 | 1 | +0.2400% | 10.84% | 38.78% |
| rank2_120_rank3_80 | FAIL | 90 | -0.0294 | $+1,140.53 | 2 | 1 | +0.3100% | 10.74% | 38.58% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Broad Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1323 | 7.2716 | +0.1393 | $154,379.70 | $156,714.64 | $+2,334.94 | 30 |
| mid_weak | 7.1660 | 7.2393 | +0.0733 | $156,462.94 | $157,718.48 | $+1,255.54 | 30 |
| old_thin | 2.0387 | 2.0450 | +0.0063 | $93,519.29 | $93,805.65 | $+286.36 | 30 |

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
  "parity_test_added": true,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "trade_enabled": false
}
```

No JavaScript was used.
