# exp-20260520-017 Broad-Market Trend-Efficiency Support Notional

Decision: `rejected_broad_market_trend_efficiency_notional`.

Single causal variable: 20-day trend-efficiency minimum for default-off broad-market paper notional support.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_trend_efficiency_support | FAIL | 0 | +0.2886 | $+1,277.48 | 2 | 1 | +1.9300% | 11.77% | 42.37% |
| trend_efficiency20_gte_0p45_scalar_1p025 | FAIL | 68 | +0.3026 | $+1,593.46 | 2 | 1 | +1.9900% | 11.59% | 42.26% |
| trend_efficiency20_gte_0p45_scalar_1p05 | FAIL | 68 | +0.3003 | $+1,909.27 | 2 | 1 | +2.0500% | 11.42% | 42.18% |
| trend_efficiency20_gte_0p45_scalar_1p075 | FAIL | 68 | +0.2892 | $+2,225.06 | 2 | 1 | +2.1100% | 11.25% | 42.10% |
| trend_efficiency20_gte_0p45_scalar_1p1 | FAIL | 68 | +0.3034 | $+2,541.13 | 2 | 1 | +2.1700% | 11.09% | 42.02% |
| trend_efficiency20_gte_0p45_scalar_1p15 | FAIL | 68 | +0.3150 | $+3,172.92 | 2 | 1 | +2.3000% | 10.78% | 41.86% |
| trend_efficiency20_gte_0p50_scalar_1p025 | FAIL | 52 | +0.3068 | $+1,644.10 | 2 | 1 | +1.9800% | 11.62% | 42.38% |
| trend_efficiency20_gte_0p50_scalar_1p05 | FAIL | 52 | +0.3328 | $+2,010.59 | 2 | 1 | +2.0400% | 11.48% | 42.41% |
| trend_efficiency20_gte_0p50_scalar_1p075 | FAIL | 52 | +0.3345 | $+2,377.05 | 2 | 1 | +2.0900% | 11.35% | 42.44% |
| trend_efficiency20_gte_0p50_scalar_1p1 | FAIL | 52 | +0.3528 | $+2,743.74 | 2 | 1 | +2.1500% | 11.21% | 42.47% |
| trend_efficiency20_gte_0p50_scalar_1p15 | FAIL | 52 | +0.4059 | $+3,476.85 | 2 | 1 | +2.2600% | 10.95% | 42.52% |
| trend_efficiency20_gte_0p55_scalar_1p025 | FAIL | 47 | +0.2853 | $+1,558.23 | 2 | 1 | +1.9800% | 11.65% | 42.28% |
| trend_efficiency20_gte_0p55_scalar_1p05 | FAIL | 47 | +0.3150 | $+1,838.86 | 2 | 1 | +2.0400% | 11.53% | 42.21% |
| trend_efficiency20_gte_0p55_scalar_1p075 | FAIL | 47 | +0.3193 | $+2,119.46 | 2 | 1 | +2.0900% | 11.41% | 42.13% |
| trend_efficiency20_gte_0p55_scalar_1p1 | FAIL | 47 | +0.3162 | $+2,400.26 | 2 | 1 | +2.1400% | 11.30% | 42.06% |
| trend_efficiency20_gte_0p55_scalar_1p15 | FAIL | 47 | +0.3591 | $+2,961.65 | 2 | 1 | +2.2500% | 11.08% | 41.93% |
| trend_efficiency20_gte_0p60_scalar_1p025 | FAIL | 39 | +0.2913 | $+1,368.29 | 2 | 1 | +1.9400% | 11.69% | 42.23% |
| trend_efficiency20_gte_0p60_scalar_1p05 | FAIL | 39 | +0.2777 | $+1,458.98 | 2 | 1 | +1.9500% | 11.61% | 42.11% |
| trend_efficiency20_gte_0p60_scalar_1p075 | FAIL | 39 | +0.2806 | $+1,549.66 | 2 | 1 | +1.9700% | 11.53% | 41.98% |
| trend_efficiency20_gte_0p60_scalar_1p1 | FAIL | 39 | +0.2833 | $+1,640.51 | 2 | 1 | +1.9800% | 11.46% | 41.86% |
| trend_efficiency20_gte_0p60_scalar_1p15 | FAIL | 39 | +0.2725 | $+1,822.01 | 2 | 1 | +2.0000% | 11.31% | 41.63% |
| trend_efficiency20_gte_0p65_scalar_1p025 | FAIL | 33 | +0.2976 | $+1,506.58 | 2 | 1 | +1.9400% | 11.69% | 42.23% |
| trend_efficiency20_gte_0p65_scalar_1p05 | FAIL | 33 | +0.3065 | $+1,735.59 | 2 | 1 | +1.9500% | 11.61% | 42.11% |
| trend_efficiency20_gte_0p65_scalar_1p075 | FAIL | 33 | +0.3156 | $+1,964.60 | 2 | 1 | +1.9600% | 11.54% | 42.00% |
| trend_efficiency20_gte_0p65_scalar_1p1 | FAIL | 33 | +0.3246 | $+2,193.73 | 2 | 1 | +1.9700% | 11.46% | 41.88% |
| trend_efficiency20_gte_0p65_scalar_1p15 | FAIL | 33 | +0.3428 | $+2,651.85 | 2 | 1 | +2.0000% | 11.32% | 41.65% |
| trend_efficiency20_gte_0p70_scalar_1p025 | FAIL | 22 | +0.2915 | $+1,383.02 | 2 | 1 | +1.9300% | 11.72% | 42.33% |
| trend_efficiency20_gte_0p70_scalar_1p05 | FAIL | 22 | +0.2944 | $+1,488.53 | 2 | 1 | +1.9300% | 11.67% | 42.31% |
| trend_efficiency20_gte_0p70_scalar_1p075 | FAIL | 22 | +0.2973 | $+1,594.02 | 2 | 1 | +1.9300% | 11.62% | 42.29% |
| trend_efficiency20_gte_0p70_scalar_1p1 | FAIL | 22 | +0.3001 | $+1,699.58 | 2 | 1 | +1.9300% | 11.57% | 42.27% |
| trend_efficiency20_gte_0p70_scalar_1p15 | FAIL | 22 | +0.2896 | $+1,910.62 | 2 | 1 | +1.9300% | 11.47% | 42.23% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.7764 | +0.3574 | $159,891.81 | $166,161.90 | $+6,270.09 |
| mid_weak | 7.3451 | 7.6646 | +0.3195 | $160,023.22 | $164,831.01 | $+4,807.79 |
| old_thin | 2.0757 | 1.8047 | -0.2710 | $94,782.99 | $87,181.96 | $-7,601.03 |

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
