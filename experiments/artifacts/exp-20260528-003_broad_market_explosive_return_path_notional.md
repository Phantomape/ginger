# exp-20260528-003 Broad-Market Explosive Return-Path Support Notional

Decision: `rejected_broad_market_explosive_return_path_notional`.

Single causal variable: max-positive-day share support scalar for default-off broad-market paper notional.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_explosive_return_path_support | FAIL | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% | 13.52% | 42.72% |
| maxposshare20_gte_0p45_scalar_1p025 | FAIL | 25 | +0.0148 | +0.09% | $+418.04 | 3 | 0 | +0.0000% | 13.72% | 42.86% |
| maxposshare20_gte_0p45_scalar_1p05 | FAIL | 25 | +0.0297 | +0.18% | $+836.03 | 3 | 0 | +0.0100% | 13.91% | 42.99% |
| maxposshare20_gte_0p45_scalar_1p075 | FAIL | 25 | +0.0286 | +0.17% | $+1,253.99 | 2 | 1 | +0.0100% | 14.10% | 43.12% |
| maxposshare20_gte_0p45_scalar_1p1 | FAIL | 25 | +0.0434 | +0.26% | $+1,672.03 | 2 | 1 | +0.0100% | 14.28% | 43.25% |
| maxposshare20_gte_0p45_scalar_1p15 | FAIL | 25 | +0.0667 | +0.40% | $+2,508.06 | 2 | 1 | +0.0100% | 14.64% | 43.51% |
| maxposshare20_gte_0p45_scalar_1p25 | FAIL | 25 | +0.0877 | +0.52% | $+4,180.08 | 2 | 1 | +0.0200% | 15.32% | 43.98% |
| maxposshare20_gte_0p45_scalar_1p5 | FAIL | 25 | +0.1655 | +0.98% | $+8,360.13 | 2 | 1 | +0.0900% | 16.81% | 45.04% |
| maxposshare20_gte_0p45_scalar_2 | FAIL | 25 | +0.2909 | +1.73% | $+16,720.26 | 2 | 1 | +0.2400% | 19.13% | 47.52% |
| maxposshare20_gte_0p50_scalar_1p025 | FAIL | 18 | +0.0145 | +0.09% | $+392.83 | 3 | 0 | +0.0000% | 13.74% | 42.93% |
| maxposshare20_gte_0p50_scalar_1p05 | FAIL | 18 | +0.0291 | +0.17% | $+785.65 | 3 | 0 | +0.0000% | 13.96% | 43.14% |
| maxposshare20_gte_0p50_scalar_1p075 | FAIL | 18 | +0.0277 | +0.16% | $+1,178.44 | 2 | 1 | +0.0100% | 14.17% | 43.35% |
| maxposshare20_gte_0p50_scalar_1p1 | FAIL | 18 | +0.0422 | +0.25% | $+1,571.29 | 2 | 1 | +0.0100% | 14.38% | 43.55% |
| maxposshare20_gte_0p50_scalar_1p15 | FAIL | 18 | +0.0650 | +0.39% | $+2,356.94 | 2 | 1 | +0.0100% | 14.79% | 43.95% |
| maxposshare20_gte_0p50_scalar_1p25 | FAIL | 18 | +0.1008 | +0.60% | $+3,928.21 | 2 | 1 | +0.0600% | 15.57% | 44.71% |
| maxposshare20_gte_0p50_scalar_1p5 | FAIL | 18 | +0.2017 | +1.20% | $+7,856.42 | 2 | 1 | +0.1700% | 17.32% | 46.40% |
| maxposshare20_gte_0p50_scalar_2 | FAIL | 18 | +0.3446 | +2.05% | $+15,712.84 | 2 | 1 | +0.3800% | 20.15% | 49.68% |
| maxposshare20_gte_0p55_scalar_1p025 | FAIL | 11 | +0.0137 | +0.08% | $+344.78 | 3 | 0 | +0.0000% | 13.76% | 42.98% |
| maxposshare20_gte_0p55_scalar_1p05 | FAIL | 11 | +0.0273 | +0.16% | $+689.55 | 3 | 0 | +0.0000% | 13.99% | 43.24% |
| maxposshare20_gte_0p55_scalar_1p075 | FAIL | 11 | +0.0249 | +0.15% | $+1,034.29 | 2 | 1 | +0.0000% | 14.22% | 43.49% |
| maxposshare20_gte_0p55_scalar_1p1 | FAIL | 11 | +0.0546 | +0.32% | $+1,379.07 | 2 | 1 | +0.0100% | 14.44% | 43.74% |
| maxposshare20_gte_0p55_scalar_1p15 | FAIL | 11 | +0.0659 | +0.39% | $+2,068.63 | 2 | 1 | +0.0100% | 14.88% | 44.23% |
| maxposshare20_gte_0p55_scalar_1p25 | FAIL | 11 | +0.1141 | +0.68% | $+3,447.68 | 2 | 1 | +0.0600% | 15.73% | 45.17% |
| maxposshare20_gte_0p55_scalar_1p5 | FAIL | 11 | +0.2123 | +1.26% | $+6,895.35 | 2 | 1 | +0.1700% | 17.65% | 47.30% |
| maxposshare20_gte_0p55_scalar_2 | FAIL | 11 | +0.3760 | +2.23% | $+13,790.71 | 2 | 1 | +0.3800% | 20.84% | 51.38% |
| maxposshare20_gte_0p60_scalar_1p025 | FAIL | 9 | +0.0023 | +0.01% | $+71.44 | 2 | 1 | +0.0000% | 13.48% | 42.82% |
| maxposshare20_gte_0p60_scalar_1p05 | FAIL | 9 | +0.0047 | +0.03% | $+142.87 | 2 | 1 | +0.0000% | 13.44% | 42.93% |
| maxposshare20_gte_0p60_scalar_1p075 | FAIL | 9 | -0.0089 | -0.05% | $+214.29 | 2 | 1 | +0.0000% | 13.39% | 43.04% |
| maxposshare20_gte_0p60_scalar_1p1 | FAIL | 9 | +0.0095 | +0.06% | $+285.74 | 2 | 1 | +0.0100% | 13.35% | 43.14% |
| maxposshare20_gte_0p60_scalar_1p15 | FAIL | 9 | -0.0016 | -0.01% | $+428.62 | 2 | 1 | +0.0100% | 13.27% | 43.35% |
| maxposshare20_gte_0p60_scalar_1p25 | FAIL | 9 | -0.0077 | -0.05% | $+714.35 | 2 | 1 | +0.0200% | 13.10% | 43.75% |
| maxposshare20_gte_0p60_scalar_1p5 | FAIL | 9 | -0.0197 | -0.12% | $+1,428.70 | 2 | 1 | +0.0400% | 13.75% | 44.73% |
| maxposshare20_gte_0p60_scalar_2 | FAIL | 9 | -0.0316 | -0.19% | $+2,857.39 | 2 | 1 | +0.0700% | 17.29% | 46.51% |
| maxposshare20_gte_0p65_scalar_1p025 | FAIL | 7 | -0.0057 | -0.03% | $-120.72 | 1 | 1 | +0.0000% | 13.52% | 42.71% |
| maxposshare20_gte_0p65_scalar_1p05 | FAIL | 7 | -0.0112 | -0.07% | $-241.44 | 1 | 1 | +0.0000% | 13.52% | 42.70% |
| maxposshare20_gte_0p65_scalar_1p075 | FAIL | 7 | -0.0328 | -0.19% | $-362.16 | 1 | 1 | +0.0000% | 13.51% | 42.69% |
| maxposshare20_gte_0p65_scalar_1p1 | FAIL | 7 | -0.0385 | -0.23% | $-482.87 | 1 | 1 | +0.0100% | 13.51% | 42.68% |
| maxposshare20_gte_0p65_scalar_1p15 | FAIL | 7 | -0.0655 | -0.39% | $-724.31 | 1 | 1 | +0.0100% | 13.50% | 42.67% |
| maxposshare20_gte_0p65_scalar_1p25 | FAIL | 7 | -0.1196 | -0.71% | $-1,207.19 | 1 | 1 | +0.0200% | 13.49% | 42.63% |
| maxposshare20_gte_0p65_scalar_1p5 | FAIL | 7 | -0.2538 | -1.51% | $-2,414.40 | 1 | 1 | +0.0400% | 13.47% | 42.55% |
| maxposshare20_gte_0p65_scalar_2 | FAIL | 7 | -0.5186 | -3.08% | $-4,828.80 | 1 | 1 | +0.0700% | 13.42% | 42.38% |
| maxposshare20_gte_0p70_scalar_1p025 | FAIL | 7 | -0.0057 | -0.03% | $-120.72 | 1 | 1 | +0.0000% | 13.52% | 42.71% |
| maxposshare20_gte_0p70_scalar_1p05 | FAIL | 7 | -0.0112 | -0.07% | $-241.44 | 1 | 1 | +0.0000% | 13.52% | 42.70% |
| maxposshare20_gte_0p70_scalar_1p075 | FAIL | 7 | -0.0328 | -0.19% | $-362.16 | 1 | 1 | +0.0000% | 13.51% | 42.69% |
| maxposshare20_gte_0p70_scalar_1p1 | FAIL | 7 | -0.0385 | -0.23% | $-482.87 | 1 | 1 | +0.0100% | 13.51% | 42.68% |
| maxposshare20_gte_0p70_scalar_1p15 | FAIL | 7 | -0.0655 | -0.39% | $-724.31 | 1 | 1 | +0.0100% | 13.50% | 42.67% |
| maxposshare20_gte_0p70_scalar_1p25 | FAIL | 7 | -0.1196 | -0.71% | $-1,207.19 | 1 | 1 | +0.0200% | 13.49% | 42.63% |
| maxposshare20_gte_0p70_scalar_1p5 | FAIL | 7 | -0.2538 | -1.51% | $-2,414.40 | 1 | 1 | +0.0400% | 13.47% | 42.55% |
| maxposshare20_gte_0p70_scalar_2 | FAIL | 7 | -0.5186 | -3.08% | $-4,828.80 | 1 | 1 | +0.0700% | 13.42% | 42.38% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4264 | +0.0074 | $159,891.81 | $160,051.96 | $+160.15 |
| mid_weak | 7.3451 | 7.3594 | +0.0143 | $160,023.22 | $160,336.10 | $+312.88 |
| old_thin | 2.0757 | 2.0837 | +0.0080 | $94,782.99 | $95,145.99 | $+363.00 |

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
  "promotion_policy": "Rejected variants are not promoted. A future positive version would need the same field and scalar implemented in quant/broad_market_paper_sleeve.py with parity tests before retention.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
