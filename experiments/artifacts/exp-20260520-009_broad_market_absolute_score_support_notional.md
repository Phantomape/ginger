# exp-20260520-009 Broad-Market Absolute-Score Support Notional

Decision: `rejected_broad_market_absolute_score_support_notional`.

Single causal variable: composite-score minimum for default-off broad-market paper notional support.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_absolute_score_support | FAIL | 0 | +0.2886 | $+1,277.48 | 2 | 1 | +1.9300% | 11.77% | 42.37% |
| score_gte_0p40_scalar_1p025 | FAIL | 87 | +0.3093 | $+2,024.44 | 2 | 1 | +1.9900% | 11.77% | 42.38% |
| score_gte_0p40_scalar_1p05 | FAIL | 87 | +0.3376 | $+2,771.18 | 2 | 1 | +2.0400% | 11.77% | 42.39% |
| score_gte_0p40_scalar_1p075 | FAIL | 87 | +0.3581 | $+3,517.88 | 2 | 1 | +2.1000% | 11.78% | 42.40% |
| score_gte_0p40_scalar_1p1 | FAIL | 87 | +0.3699 | $+4,264.92 | 2 | 1 | +2.1600% | 11.78% | 42.41% |
| score_gte_0p40_scalar_1p15 | FAIL | 87 | +0.4274 | $+5,758.62 | 2 | 1 | +2.2800% | 11.78% | 42.43% |
| score_gte_0p50_scalar_1p025 | FAIL | 79 | +0.3107 | $+2,094.69 | 2 | 1 | +1.9900% | 11.77% | 42.39% |
| score_gte_0p50_scalar_1p05 | FAIL | 79 | +0.3406 | $+2,911.71 | 2 | 1 | +2.0400% | 11.78% | 42.41% |
| score_gte_0p50_scalar_1p075 | FAIL | 79 | +0.3625 | $+3,728.70 | 2 | 1 | +2.1000% | 11.78% | 42.42% |
| score_gte_0p50_scalar_1p1 | FAIL | 79 | +0.3845 | $+4,545.98 | 2 | 1 | +2.1600% | 11.79% | 42.44% |
| score_gte_0p50_scalar_1p15 | FAIL | 79 | +0.4527 | $+6,180.23 | 2 | 1 | +2.2800% | 11.79% | 42.47% |
| score_gte_0p60_scalar_1p025 | FAIL | 63 | +0.3323 | $+2,177.43 | 2 | 1 | +1.9800% | 11.79% | 42.45% |
| score_gte_0p60_scalar_1p05 | FAIL | 63 | +0.3673 | $+3,077.23 | 2 | 1 | +2.0300% | 11.81% | 42.53% |
| score_gte_0p60_scalar_1p075 | FAIL | 63 | +0.4277 | $+3,977.00 | 2 | 1 | +2.0800% | 11.83% | 42.61% |
| score_gte_0p60_scalar_1p1 | FAIL | 63 | +0.4714 | $+4,877.01 | 2 | 1 | +2.1400% | 11.85% | 42.68% |
| score_gte_0p60_scalar_1p15 | FAIL | 63 | +0.5670 | $+6,676.77 | 2 | 1 | +2.2400% | 11.89% | 42.82% |
| score_gte_0p70_scalar_1p025 | FAIL | 51 | +0.3192 | $+1,897.19 | 2 | 1 | +1.9800% | 11.84% | 42.61% |
| score_gte_0p70_scalar_1p05 | FAIL | 51 | +0.3244 | $+2,516.78 | 2 | 1 | +2.0300% | 11.91% | 42.86% |
| score_gte_0p70_scalar_1p075 | FAIL | 51 | +0.3384 | $+3,136.32 | 2 | 1 | +2.0800% | 11.97% | 43.11% |
| score_gte_0p70_scalar_1p1 | FAIL | 51 | +0.3690 | $+3,756.08 | 2 | 1 | +2.1300% | 12.04% | 43.34% |
| score_gte_0p70_scalar_1p15 | FAIL | 51 | +0.3879 | $+4,995.38 | 2 | 1 | +2.2400% | 12.16% | 43.78% |
| score_gte_0p80_scalar_1p025 | FAIL | 36 | +0.3079 | $+1,658.34 | 2 | 1 | +1.9800% | 11.89% | 42.61% |
| score_gte_0p80_scalar_1p05 | FAIL | 36 | +0.2855 | $+2,039.15 | 2 | 1 | +2.0300% | 12.01% | 42.85% |
| score_gte_0p80_scalar_1p075 | FAIL | 36 | +0.2883 | $+2,419.89 | 2 | 1 | +2.0800% | 12.13% | 43.09% |
| score_gte_0p80_scalar_1p1 | FAIL | 36 | +0.3076 | $+2,800.80 | 2 | 1 | +2.1200% | 12.24% | 43.32% |
| score_gte_0p80_scalar_1p15 | FAIL | 36 | +0.2876 | $+3,562.46 | 2 | 1 | +2.2200% | 12.46% | 43.77% |
| score_gte_0p90_scalar_1p025 | FAIL | 29 | +0.2790 | $+1,393.62 | 2 | 1 | +1.9800% | 11.94% | 42.57% |
| score_gte_0p90_scalar_1p05 | FAIL | 29 | +0.2605 | $+1,509.75 | 2 | 1 | +2.0300% | 12.10% | 42.78% |
| score_gte_0p90_scalar_1p075 | FAIL | 29 | +0.2344 | $+1,625.81 | 2 | 1 | +2.0800% | 12.27% | 42.98% |
| score_gte_0p90_scalar_1p1 | FAIL | 29 | +0.2410 | $+1,742.01 | 2 | 1 | +2.1200% | 12.43% | 43.18% |
| score_gte_0p90_scalar_1p15 | FAIL | 29 | +0.1886 | $+1,974.27 | 2 | 1 | +2.2200% | 12.74% | 43.57% |
| score_gte_1p00_scalar_1p025 | FAIL | 21 | +0.2826 | $+1,503.95 | 2 | 1 | +1.9700% | 11.96% | 42.64% |
| score_gte_1p00_scalar_1p05 | FAIL | 21 | +0.2931 | $+1,730.40 | 2 | 1 | +2.0100% | 12.14% | 42.92% |
| score_gte_1p00_scalar_1p075 | FAIL | 21 | +0.2873 | $+1,956.79 | 2 | 1 | +2.0500% | 12.33% | 43.19% |
| score_gte_1p00_scalar_1p1 | FAIL | 21 | +0.2727 | $+2,183.29 | 2 | 1 | +2.0900% | 12.51% | 43.46% |
| score_gte_1p00_scalar_1p15 | FAIL | 21 | +0.2774 | $+2,636.21 | 2 | 1 | +2.1800% | 12.86% | 43.99% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.7972 | +0.3782 | $159,891.81 | $167,322.59 | $+7,430.78 |
| mid_weak | 7.3451 | 7.8169 | +0.4718 | $160,023.22 | $167,026.97 | $+7,003.75 |
| old_thin | 2.0757 | 1.7927 | -0.2830 | $94,782.99 | $87,025.23 | $-7,757.76 |

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
