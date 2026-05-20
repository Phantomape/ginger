# exp-20260520-006 State-Surface Trend-Stability Support Notional

Decision: `rejected_state_surface_trend_stability_support_notional`.

Single causal variable: `trend_stability_support_notional_scalar` for already-selected default-off state-surface paper candidates with `ret20_excess_spy - ret60 / 3 <= max_acceleration`.

State-surface scalar Gate 4 is strict here: aggregate EV delta pct must be `> 10%` before a production-visible scalar can be retained.

## Sweep

| Variant | Gate 4 | Max Accel | Scalar | dEV | dEV % | dPnL | EV Improved | EV Regressed | PnL Regressed | Adjusted Trades | Max DD Worse | Single Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_low_extension_support_notional | FAIL | n/a | n/a | +0.0000 | +0.00% | $+0.00 | 0 | 0 | 0 | 0 | +0.0000% | 44.48% |
| accel_le_0p0_scalar_1p025 | FAIL | 0.0 | 1.025 | +0.0738 | +0.47% | $+1,436.59 | 3 | 0 | 0 | 8 | +0.0000% | 44.60% |
| accel_le_0p0_scalar_1p05 | FAIL | 0.0 | 1.05 | +0.1572 | +0.99% | $+2,873.17 | 3 | 0 | 0 | 8 | +0.0000% | 44.72% |
| accel_le_0p0_scalar_1p075 | FAIL | 0.0 | 1.075 | +0.2468 | +1.56% | $+4,309.76 | 3 | 0 | 0 | 8 | +0.0000% | 44.83% |
| accel_le_0p0_scalar_1p1 | FAIL | 0.0 | 1.1 | +0.3216 | +2.03% | $+5,746.34 | 3 | 0 | 0 | 8 | +0.0000% | 44.94% |
| accel_le_0p0_scalar_1p15 | FAIL | 0.0 | 1.15 | +0.4810 | +3.03% | $+8,619.53 | 3 | 0 | 0 | 8 | +0.0000% | 45.16% |
| accel_le_0p03_scalar_1p025 | FAIL | 0.03 | 1.025 | +0.0747 | +0.47% | $+1,490.83 | 3 | 0 | 0 | 11 | +0.0000% | 44.58% |
| accel_le_0p03_scalar_1p05 | FAIL | 0.03 | 1.05 | +0.1590 | +1.00% | $+2,981.65 | 3 | 0 | 0 | 11 | +0.0100% | 44.68% |
| accel_le_0p03_scalar_1p075 | FAIL | 0.03 | 1.075 | +0.2494 | +1.57% | $+4,472.48 | 3 | 0 | 0 | 11 | +0.0100% | 44.78% |
| accel_le_0p03_scalar_1p1 | FAIL | 0.03 | 1.1 | +0.3344 | +2.11% | $+5,963.31 | 3 | 0 | 0 | 11 | +0.0100% | 44.87% |
| accel_le_0p03_scalar_1p15 | FAIL | 0.03 | 1.15 | +0.4808 | +3.03% | $+8,944.96 | 2 | 1 | 0 | 11 | +0.0200% | 45.06% |
| accel_le_0p06_scalar_1p025 | FAIL | 0.06 | 1.025 | +0.0842 | +0.53% | $+1,690.07 | 3 | 0 | 0 | 13 | +0.0000% | 44.53% |
| accel_le_0p06_scalar_1p05 | FAIL | 0.06 | 1.05 | +0.1781 | +1.12% | $+3,380.12 | 3 | 0 | 0 | 13 | +0.0100% | 44.57% |
| accel_le_0p06_scalar_1p075 | FAIL | 0.06 | 1.075 | +0.2779 | +1.75% | $+5,070.20 | 3 | 0 | 0 | 13 | +0.0100% | 44.62% |
| accel_le_0p06_scalar_1p1 | FAIL | 0.06 | 1.1 | +0.3724 | +2.35% | $+6,760.27 | 3 | 0 | 0 | 13 | +0.0100% | 44.66% |
| accel_le_0p06_scalar_1p15 | FAIL | 0.06 | 1.15 | +0.5528 | +3.49% | $+10,140.40 | 3 | 0 | 0 | 13 | +0.0200% | 44.74% |
| accel_le_0p09_scalar_1p025 | FAIL | 0.09 | 1.025 | +0.1275 | +0.80% | $+3,136.67 | 3 | 0 | 0 | 16 | +0.1100% | 44.73% |
| accel_le_0p09_scalar_1p05 | FAIL | 0.09 | 1.05 | +0.2800 | +1.77% | $+6,273.35 | 3 | 0 | 0 | 16 | +0.2200% | 44.97% |
| accel_le_0p09_scalar_1p075 | FAIL | 0.09 | 1.075 | +0.4233 | +2.67% | $+9,410.03 | 3 | 0 | 0 | 16 | +0.3200% | 45.20% |
| accel_le_0p09_scalar_1p1 | FAIL | 0.09 | 1.1 | +0.5520 | +3.48% | $+12,546.71 | 3 | 0 | 0 | 16 | +0.4300% | 45.43% |
| accel_le_0p09_scalar_1p15 | FAIL | 0.09 | 1.15 | +0.8352 | +5.27% | $+18,820.06 | 3 | 0 | 0 | 16 | +0.6500% | 45.85% |
| accel_le_0p12_scalar_1p025 | FAIL | 0.12 | 1.025 | +0.1251 | +0.79% | $+3,082.90 | 3 | 0 | 0 | 18 | +0.1100% | 44.72% |
| accel_le_0p12_scalar_1p05 | FAIL | 0.12 | 1.05 | +0.2751 | +1.74% | $+6,165.81 | 3 | 0 | 0 | 18 | +0.2200% | 44.95% |
| accel_le_0p12_scalar_1p075 | FAIL | 0.12 | 1.075 | +0.4008 | +2.53% | $+9,248.72 | 3 | 0 | 0 | 18 | +0.3200% | 45.18% |
| accel_le_0p12_scalar_1p1 | FAIL | 0.12 | 1.1 | +0.5269 | +3.32% | $+12,331.63 | 3 | 0 | 0 | 18 | +0.4300% | 45.39% |
| accel_le_0p12_scalar_1p15 | FAIL | 0.12 | 1.15 | +0.8049 | +5.08% | $+18,497.44 | 3 | 0 | 0 | 18 | +0.6500% | 45.80% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1279 | 7.1989 | +0.0710 | $149,745.91 | $151,236.86 | $+1,490.95 | 8.39% | 8.41% | 5 |
| mid_weak | 6.6874 | 7.0977 | +0.4103 | $148,278.86 | $154,970.82 | $+6,691.96 | 10.10% | 10.10% | 6 |
| old_thin | 2.0377 | 2.1092 | +0.0715 | $92,623.34 | $94,580.83 | $+1,957.49 | 11.64% | 11.11% | 2 |

## Production Impact

```json
{
  "backtester_adapter_changed": false,
  "core_metrics_changed": false,
  "default_off_paper_only": true,
  "live_default_orders_changed": false,
  "parity_test_added": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
