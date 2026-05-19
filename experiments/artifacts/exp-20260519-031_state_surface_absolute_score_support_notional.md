# exp-20260519-031 State-Surface Absolute Score Support Notional

Decision: `accepted_default_off_state_surface_absolute_score_support_notional`.

Single causal variable: `absolute_score_support_notional_profile` for already-selected default-off state-surface paper candidates.

## Sweep

| Variant | Gate 4 | Score min | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_queue_lag_support_notional | FAIL | n/a | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% | 41.03% |
| score_ge_0p9_scalar_1p05 | PASS | 0.9 | 1.05 | +0.2333 | $+4,838.99 | 3 | 0 | 16 | +0.1500% | 41.50% |
| score_ge_0p9_scalar_1p1 | PASS | 0.9 | 1.1 | +0.4392 | $+9,677.95 | 3 | 0 | 16 | +0.3000% | 41.95% |
| score_ge_0p9_scalar_1p15 | PASS | 0.9 | 1.15 | +0.6845 | $+14,516.94 | 3 | 0 | 16 | +0.4600% | 42.36% |
| score_ge_0p9_scalar_1p2 | FAIL | 0.9 | 1.2 | +0.8990 | $+19,355.92 | 3 | 0 | 16 | +0.6100% | 42.74% |
| score_ge_0p9_scalar_1p25 | FAIL | 0.9 | 1.25 | +1.1090 | $+24,194.91 | 3 | 0 | 16 | +0.7600% | 43.10% |
| score_ge_1p0_scalar_1p05 | PASS | 1.0 | 1.05 | +0.2160 | $+4,765.73 | 3 | 0 | 15 | +0.1500% | 41.52% |
| score_ge_1p0_scalar_1p1 | PASS | 1.0 | 1.1 | +0.4327 | $+9,531.42 | 3 | 0 | 15 | +0.3000% | 41.98% |
| score_ge_1p0_scalar_1p15 | PASS | 1.0 | 1.15 | +0.6747 | $+14,297.14 | 3 | 0 | 15 | +0.4600% | 42.42% |
| score_ge_1p0_scalar_1p2 | FAIL | 1.0 | 1.2 | +0.8713 | $+19,062.86 | 3 | 0 | 15 | +0.6100% | 42.82% |
| score_ge_1p0_scalar_1p25 | FAIL | 1.0 | 1.25 | +1.0777 | $+23,828.58 | 3 | 0 | 15 | +0.7600% | 43.20% |
| score_ge_1p1_scalar_1p05 | PASS | 1.1 | 1.05 | +0.1916 | $+4,209.58 | 3 | 0 | 14 | +0.1500% | 41.30% |
| score_ge_1p1_scalar_1p1 | PASS | 1.1 | 1.1 | +0.3554 | $+8,419.13 | 3 | 0 | 14 | +0.3000% | 41.56% |
| score_ge_1p1_scalar_1p15 | PASS | 1.1 | 1.15 | +0.5578 | $+12,628.71 | 3 | 0 | 14 | +0.4600% | 41.81% |
| score_ge_1p1_scalar_1p2 | FAIL | 1.1 | 1.2 | +0.7144 | $+16,838.28 | 3 | 0 | 14 | +0.6100% | 42.04% |
| score_ge_1p1_scalar_1p25 | FAIL | 1.1 | 1.25 | +0.8949 | $+21,047.85 | 3 | 0 | 14 | +0.7600% | 42.26% |
| score_ge_1p2_scalar_1p05 | PASS | 1.2 | 1.05 | +0.1261 | $+3,348.92 | 3 | 0 | 13 | +0.1500% | 40.96% |
| score_ge_1p2_scalar_1p1 | PASS | 1.2 | 1.1 | +0.2379 | $+6,697.81 | 3 | 0 | 13 | +0.3000% | 40.90% |
| score_ge_1p2_scalar_1p15 | PASS | 1.2 | 1.15 | +0.3878 | $+10,046.72 | 3 | 0 | 13 | +0.4600% | 40.85% |
| score_ge_1p2_scalar_1p2 | FAIL | 1.2 | 1.2 | +0.4918 | $+13,395.63 | 3 | 0 | 13 | +0.6100% | 40.79% |
| score_ge_1p2_scalar_1p25 | FAIL | 1.2 | 1.25 | +0.6050 | $+16,744.54 | 3 | 0 | 13 | +0.7600% | 40.74% |
| score_ge_1p3_scalar_1p05 | PASS | 1.3 | 1.05 | +0.1187 | $+3,194.12 | 3 | 0 | 10 | +0.1500% | 41.01% |
| score_ge_1p3_scalar_1p1 | PASS | 1.3 | 1.1 | +0.2232 | $+6,388.21 | 3 | 0 | 10 | +0.3000% | 41.00% |
| score_ge_1p3_scalar_1p15 | PASS | 1.3 | 1.15 | +0.3508 | $+9,582.32 | 3 | 0 | 10 | +0.4600% | 40.99% |
| score_ge_1p3_scalar_1p2 | FAIL | 1.3 | 1.2 | +0.4474 | $+12,776.43 | 3 | 0 | 10 | +0.6100% | 40.98% |
| score_ge_1p3_scalar_1p25 | FAIL | 1.3 | 1.25 | +0.5682 | $+15,970.54 | 3 | 0 | 10 | +0.7600% | 40.97% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.9653 | 7.1075 | +0.1422 | $146,946.35 | $149,317.03 | $+2,370.68 | 8.00% | 8.38% | 6 |
| mid_weak | 6.0438 | 6.4151 | +0.3713 | $138,301.35 | $144,158.66 | $+5,857.31 | 10.12% | 10.10% | 7 |
| old_thin | 1.7624 | 1.9334 | +0.1710 | $81,594.32 | $87,883.27 | $+6,288.95 | 10.33% | 10.79% | 3 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": true,
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true
}
```

No JavaScript was used.
