# exp-20260520-002 Broad-Market Low-Extension Notional

Decision: `accepted_default_off_broad_market_low_extension_notional`.

Single causal variable: low-ret5 paper-notional support on the fixed exp-20260519-037 broad-market paper sleeve.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_low_extension | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 12.24% | 42.63% |
| ret5_le_0p00_scalar_1p05 | FAIL | 5 | +0.0001 | $+7.92 | 1 | 0 | +0.0000% | 12.23% | 42.58% |
| ret5_le_0p00_scalar_1p10 | FAIL | 5 | +0.0005 | $+15.83 | 3 | 0 | +0.0000% | 12.21% | 42.53% |
| ret5_le_0p00_scalar_1p15 | FAIL | 5 | +0.0007 | $+23.73 | 3 | 0 | +0.0000% | 12.20% | 42.48% |
| ret5_le_0p02_scalar_1p025 | PASS | 12 | +0.0048 | $+132.12 | 3 | 0 | +0.0000% | 12.20% | 42.51% |
| ret5_le_0p02_scalar_1p05 | PASS | 12 | +0.0097 | $+264.24 | 3 | 0 | +0.0000% | 12.17% | 42.38% |
| ret5_le_0p02_scalar_1p075 | PASS | 12 | +0.0240 | $+396.35 | 3 | 0 | +0.0000% | 12.13% | 42.25% |
| ret5_le_0p02_scalar_1p10 | PASS | 12 | +0.0289 | $+528.46 | 3 | 0 | +0.0000% | 12.09% | 42.13% |
| ret5_le_0p02_scalar_1p15 | PASS | 12 | +0.0545 | $+792.70 | 3 | 0 | +0.0000% | 12.02% | 41.88% |
| ret5_le_0p05_scalar_1p025 | FAIL | 30 | +0.0035 | $+105.37 | 2 | 1 | +0.0000% | 12.18% | 42.44% |
| ret5_le_0p05_scalar_1p05 | FAIL | 30 | +0.0072 | $+210.74 | 2 | 1 | +0.0000% | 12.13% | 42.24% |
| ret5_le_0p05_scalar_1p075 | FAIL | 30 | +0.0202 | $+316.11 | 2 | 1 | +0.0000% | 12.07% | 42.05% |
| ret5_le_0p05_scalar_1p10 | FAIL | 30 | +0.0239 | $+421.48 | 2 | 1 | +0.0000% | 12.02% | 41.86% |
| ret5_le_0p05_scalar_1p15 | FAIL | 30 | +0.0155 | $+632.22 | 2 | 1 | +0.0000% | 11.91% | 41.48% |
| ret5_le_0p08_scalar_1p025 | FAIL | 42 | +0.0086 | $+218.01 | 2 | 1 | +0.0000% | 12.14% | 42.54% |
| ret5_le_0p08_scalar_1p05 | FAIL | 42 | +0.0174 | $+436.02 | 2 | 1 | +0.0000% | 12.04% | 42.44% |
| ret5_le_0p08_scalar_1p075 | FAIL | 42 | +0.0198 | $+654.04 | 2 | 1 | -0.0100% | 11.95% | 42.35% |
| ret5_le_0p08_scalar_1p10 | FAIL | 42 | +0.0444 | $+872.06 | 2 | 1 | -0.0100% | 11.85% | 42.25% |
| ret5_le_0p08_scalar_1p15 | FAIL | 42 | +0.0464 | $+1,308.09 | 2 | 1 | -0.0100% | 11.67% | 42.07% |
| ret5_le_0p10_scalar_1p025 | FAIL | 48 | +0.0070 | $+165.24 | 2 | 1 | +0.0000% | 12.12% | 42.58% |
| ret5_le_0p10_scalar_1p05 | FAIL | 48 | +0.0140 | $+330.49 | 2 | 1 | +0.0100% | 12.01% | 42.53% |
| ret5_le_0p10_scalar_1p075 | FAIL | 48 | +0.0053 | $+495.74 | 2 | 1 | +0.0200% | 11.89% | 42.48% |
| ret5_le_0p10_scalar_1p10 | FAIL | 48 | +0.0122 | $+660.97 | 2 | 1 | +0.0200% | 11.78% | 42.43% |
| ret5_le_0p10_scalar_1p15 | FAIL | 48 | +0.0200 | $+991.47 | 2 | 1 | +0.0300% | 11.56% | 42.33% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.2716 | 7.2886 | +0.0170 | $156,714.64 | $156,743.22 | $+28.58 |
| mid_weak | 7.2393 | 7.2611 | +0.0218 | $157,718.48 | $158,193.22 | $+474.74 |
| old_thin | 2.0450 | 2.0607 | +0.0157 | $93,805.65 | $94,095.03 | $+289.38 |

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
