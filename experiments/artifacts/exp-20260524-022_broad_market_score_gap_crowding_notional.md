# exp-20260524-022 Broad-Market Score-Gap Crowding Support Notional

Decision: `rejected_broad_market_score_gap_crowding_notional`.

Single causal variable: score gap to the next same-day broad-market candidate for default-off paper notional support.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_score_gap_support | FAIL | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% | 42.72% |
| score_gap_gte_0p075_scalar_1p025 | FAIL | 38 | +0.0253 | +0.15% | $+606.36 | 2 | 1 | +0.0000% | 42.96% |
| score_gap_gte_0p075_scalar_1p05 | FAIL | 38 | +0.0507 | +0.30% | $+1,212.61 | 3 | 0 | +0.0000% | 43.20% |
| score_gap_gte_0p075_scalar_1p075 | FAIL | 38 | +0.0762 | +0.45% | $+1,818.85 | 3 | 0 | +0.0200% | 43.44% |
| score_gap_gte_0p075_scalar_1p1 | FAIL | 38 | +0.1015 | +0.60% | $+2,425.23 | 3 | 0 | +0.0400% | 43.66% |
| score_gap_gte_0p075_scalar_1p15 | FAIL | 38 | +0.1523 | +0.90% | $+3,637.84 | 3 | 0 | +0.0900% | 44.10% |
| score_gap_gte_0p1_scalar_1p025 | FAIL | 25 | +0.0225 | +0.13% | $+542.56 | 2 | 1 | +0.0000% | 43.07% |
| score_gap_gte_0p1_scalar_1p05 | FAIL | 25 | +0.0451 | +0.27% | $+1,085.07 | 2 | 1 | +0.0000% | 43.41% |
| score_gap_gte_0p1_scalar_1p075 | FAIL | 25 | +0.0677 | +0.40% | $+1,627.54 | 3 | 0 | +0.0000% | 43.75% |
| score_gap_gte_0p1_scalar_1p1 | FAIL | 25 | +0.0902 | +0.54% | $+2,170.13 | 3 | 0 | +0.0000% | 44.08% |
| score_gap_gte_0p1_scalar_1p15 | FAIL | 25 | +0.1353 | +0.80% | $+3,255.20 | 3 | 0 | +0.0000% | 44.71% |
| score_gap_gte_0p125_scalar_1p025 | FAIL | 20 | +0.0193 | +0.11% | $+471.51 | 2 | 1 | +0.0000% | 43.03% |
| score_gap_gte_0p125_scalar_1p05 | FAIL | 20 | +0.0386 | +0.23% | $+942.97 | 2 | 1 | +0.0000% | 43.34% |
| score_gap_gte_0p125_scalar_1p075 | FAIL | 20 | +0.0581 | +0.34% | $+1,414.41 | 3 | 0 | +0.0000% | 43.64% |
| score_gap_gte_0p125_scalar_1p1 | FAIL | 20 | +0.0774 | +0.46% | $+1,885.93 | 3 | 0 | +0.0000% | 43.93% |
| score_gap_gte_0p125_scalar_1p15 | FAIL | 20 | +0.1161 | +0.69% | $+2,828.90 | 3 | 0 | +0.0000% | 44.50% |
| score_gap_gte_0p15_scalar_1p025 | FAIL | 16 | +0.0385 | +0.23% | $+540.27 | 3 | 0 | +0.0000% | 43.04% |
| score_gap_gte_0p15_scalar_1p05 | FAIL | 16 | +0.0609 | +0.36% | $+1,080.54 | 3 | 0 | +0.0000% | 43.37% |
| score_gap_gte_0p15_scalar_1p075 | FAIL | 16 | +0.0834 | +0.50% | $+1,620.75 | 3 | 0 | +0.0000% | 43.68% |
| score_gap_gte_0p15_scalar_1p1 | FAIL | 16 | +0.1059 | +0.63% | $+2,161.06 | 3 | 0 | +0.0000% | 43.98% |
| score_gap_gte_0p15_scalar_1p15 | FAIL | 16 | +0.1509 | +0.90% | $+3,241.60 | 3 | 0 | +0.0000% | 44.58% |
| score_gap_gte_0p175_scalar_1p025 | FAIL | 14 | +0.0394 | +0.23% | $+561.08 | 3 | 0 | +0.0000% | 43.05% |
| score_gap_gte_0p175_scalar_1p05 | FAIL | 14 | +0.0629 | +0.37% | $+1,122.17 | 3 | 0 | +0.0100% | 43.38% |
| score_gap_gte_0p175_scalar_1p075 | FAIL | 14 | +0.0863 | +0.51% | $+1,683.20 | 3 | 0 | +0.0100% | 43.69% |
| score_gap_gte_0p175_scalar_1p1 | FAIL | 14 | +0.1098 | +0.65% | $+2,244.31 | 3 | 0 | +0.0100% | 44.00% |
| score_gap_gte_0p175_scalar_1p15 | FAIL | 14 | +0.1567 | +0.93% | $+3,366.47 | 3 | 0 | +0.0200% | 44.61% |
| score_gap_gte_0p2_scalar_1p025 | FAIL | 13 | +0.0213 | +0.13% | $+515.18 | 2 | 1 | +0.0000% | 43.01% |
| score_gap_gte_0p2_scalar_1p05 | FAIL | 13 | +0.0426 | +0.25% | $+1,030.38 | 2 | 1 | +0.0100% | 43.30% |
| score_gap_gte_0p2_scalar_1p075 | FAIL | 13 | +0.0640 | +0.38% | $+1,545.51 | 3 | 0 | +0.0100% | 43.58% |
| score_gap_gte_0p2_scalar_1p1 | FAIL | 13 | +0.0853 | +0.51% | $+2,060.71 | 3 | 0 | +0.0100% | 43.85% |
| score_gap_gte_0p2_scalar_1p15 | FAIL | 13 | +0.1279 | +0.76% | $+3,091.07 | 3 | 0 | +0.0200% | 44.38% |
| score_gap_gte_0p25_scalar_1p025 | FAIL | 8 | +0.0337 | +0.20% | $+433.98 | 3 | 0 | +0.0000% | 42.94% |
| score_gap_gte_0p25_scalar_1p05 | FAIL | 8 | +0.0515 | +0.31% | $+867.98 | 3 | 0 | +0.0100% | 43.17% |
| score_gap_gte_0p25_scalar_1p075 | FAIL | 8 | +0.0692 | +0.41% | $+1,301.92 | 3 | 0 | +0.0100% | 43.39% |
| score_gap_gte_0p25_scalar_1p1 | FAIL | 8 | +0.0871 | +0.52% | $+1,735.91 | 3 | 0 | +0.0100% | 43.60% |
| score_gap_gte_0p25_scalar_1p15 | FAIL | 8 | +0.1225 | +0.73% | $+2,603.88 | 3 | 0 | +0.0200% | 44.02% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.5121 | +0.0931 | $159,891.81 | $161,550.19 | $+1,658.38 |
| mid_weak | 7.3451 | 7.3952 | +0.0501 | $160,023.22 | $161,114.79 | $+1,091.57 |
| old_thin | 2.0757 | 2.0892 | +0.0135 | $94,782.99 | $95,399.51 | $+616.52 |

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
