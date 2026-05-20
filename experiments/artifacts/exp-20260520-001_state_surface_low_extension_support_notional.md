# exp-20260520-001 State-Surface Low-Extension Support Notional

Decision: `accepted_default_off_state_surface_low_extension_support_notional`.

Single causal variable: `low_extension_support_notional_scalar` for already-selected default-off state-surface paper candidates with `ret5 <= 0.02`.

## Sweep

| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Adjusted Trades | Max DD Worse | Single Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted_rank_depth_score_volume_notional | FAIL | n/a | +0.0000 | $+0.00 | 0 | 0 | 0 | 0 | +0.0000% | 43.67% |
| ret5_le_0p02_scalar_0p95 | FAIL | 0.95 | -0.2488 | $-4,925.65 | 0 | 3 | 3 | 9 | +0.0000% | 42.80% |
| ret5_le_0p02_scalar_1p025 | PASS | 1.025 | +0.1181 | $+2,462.81 | 3 | 0 | 0 | 9 | +0.1900% | 44.08% |
| ret5_le_0p02_scalar_1p05 | PASS | 1.05 | +0.2368 | $+4,925.64 | 3 | 0 | 0 | 9 | +0.3800% | 44.48% |
| ret5_le_0p02_scalar_1p075 | FAIL | 1.075 | +0.3411 | $+7,388.46 | 2 | 1 | 0 | 9 | +0.5700% | 44.88% |
| ret5_le_0p02_scalar_1p1 | FAIL | 1.1 | +0.4609 | $+9,851.28 | 3 | 0 | 0 | 9 | +0.7600% | 45.26% |
| ret5_le_0p02_scalar_1p15 | FAIL | 1.15 | +0.6773 | $+14,776.93 | 3 | 0 | 0 | 9 | +1.1400% | 45.98% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.1202 | 7.1279 | +0.0077 | $149,584.06 | $149,745.91 | $+161.85 | 8.39% | 8.39% | 3 |
| mid_weak | 6.5001 | 6.6874 | +0.1873 | $145,415.33 | $148,278.86 | $+2,863.53 | 10.10% | 10.10% | 5 |
| old_thin | 1.9959 | 2.0377 | +0.0418 | $90,723.08 | $92,623.34 | $+1,900.26 | 11.26% | 11.64% | 1 |

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
  "shared_policy_changed": true,
  "trade_enabled": false
}
```

No JavaScript was used.
