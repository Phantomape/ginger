# exp-20260520-003 Broad-Market High-Volatility Notional

Decision: `accepted_default_off_broad_market_high_volatility_notional`.

Single causal variable: high 20-day realized-volatility paper-notional support on the fixed exp-20260520-002 broad-market paper sleeve.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_high_volatility | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 12.02% | 41.88% |
| vol20_gte_0p040_scalar_1p025 | FAIL | 24 | -0.0043 | $+275.63 | 2 | 1 | +0.0000% | 12.20% | 42.20% |
| vol20_gte_0p040_scalar_1p05 | FAIL | 24 | +0.0070 | $+551.27 | 2 | 1 | +0.0000% | 12.37% | 42.52% |
| vol20_gte_0p040_scalar_1p075 | FAIL | 24 | +0.0028 | $+826.91 | 2 | 1 | +0.0100% | 12.53% | 42.83% |
| vol20_gte_0p040_scalar_1p1 | FAIL | 24 | +0.0300 | $+1,102.55 | 2 | 1 | +0.0100% | 12.70% | 43.14% |
| vol20_gte_0p040_scalar_1p15 | FAIL | 24 | +0.0371 | $+1,653.83 | 2 | 1 | +0.0100% | 13.02% | 43.73% |
| vol20_gte_0p045_scalar_1p025 | FAIL | 18 | -0.0038 | $+282.43 | 2 | 1 | +0.0000% | 12.21% | 42.21% |
| vol20_gte_0p045_scalar_1p05 | FAIL | 18 | +0.0082 | $+564.85 | 2 | 1 | +0.0100% | 12.40% | 42.53% |
| vol20_gte_0p045_scalar_1p075 | FAIL | 18 | +0.0361 | $+847.28 | 2 | 1 | +0.0100% | 12.58% | 42.85% |
| vol20_gte_0p045_scalar_1p1 | FAIL | 18 | +0.0323 | $+1,129.71 | 2 | 1 | +0.0200% | 12.76% | 43.16% |
| vol20_gte_0p045_scalar_1p15 | FAIL | 18 | +0.0564 | $+1,694.56 | 2 | 1 | +0.0200% | 13.11% | 43.76% |
| vol20_gte_0p050_scalar_1p025 | FAIL | 12 | -0.0035 | $+289.49 | 2 | 1 | +0.0000% | 12.23% | 42.16% |
| vol20_gte_0p050_scalar_1p05 | FAIL | 12 | +0.0246 | $+578.98 | 2 | 1 | +0.0000% | 12.42% | 42.44% |
| vol20_gte_0p050_scalar_1p075 | FAIL | 12 | +0.0371 | $+868.47 | 2 | 1 | +0.0100% | 12.62% | 42.72% |
| vol20_gte_0p050_scalar_1p1 | FAIL | 12 | +0.0493 | $+1,157.96 | 2 | 1 | +0.0100% | 12.81% | 42.99% |
| vol20_gte_0p050_scalar_1p15 | FAIL | 12 | +0.0582 | $+1,736.94 | 2 | 1 | +0.0100% | 13.19% | 43.52% |
| vol20_gte_0p055_scalar_1p025 | PASS | 9 | +0.0156 | $+360.71 | 3 | 0 | +0.0000% | 12.23% | 42.12% |
| vol20_gte_0p055_scalar_1p05 | PASS | 9 | +0.0312 | $+721.42 | 3 | 0 | +0.0000% | 12.44% | 42.36% |
| vol20_gte_0p055_scalar_1p075 | PASS | 9 | +0.0628 | $+1,082.13 | 3 | 0 | +0.0100% | 12.65% | 42.60% |
| vol20_gte_0p055_scalar_1p1 | PASS | 9 | +0.0784 | $+1,442.84 | 3 | 0 | +0.0100% | 12.85% | 42.83% |
| vol20_gte_0p055_scalar_1p15 | PASS | 9 | +0.1097 | $+2,164.26 | 3 | 0 | +0.0100% | 13.25% | 43.28% |
| vol20_gte_0p060_scalar_1p025 | PASS | 8 | +0.0162 | $+373.70 | 3 | 0 | +0.0000% | 12.23% | 42.12% |
| vol20_gte_0p060_scalar_1p05 | PASS | 8 | +0.0482 | $+747.41 | 3 | 0 | +0.0000% | 12.44% | 42.36% |
| vol20_gte_0p060_scalar_1p075 | PASS | 8 | +0.0646 | $+1,121.10 | 3 | 0 | +0.0100% | 12.65% | 42.60% |
| vol20_gte_0p060_scalar_1p1 | PASS | 8 | +0.0808 | $+1,494.80 | 3 | 0 | +0.0100% | 12.85% | 42.83% |
| vol20_gte_0p060_scalar_1p15 | PASS | 8 | +0.1292 | $+2,242.21 | 3 | 0 | +0.0100% | 13.25% | 43.28% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.2886 | 7.3402 | +0.0516 | $156,743.22 | $157,853.12 | $+1,109.90 |
| mid_weak | 7.2611 | 7.3136 | +0.0525 | $158,193.22 | $158,992.04 | $+798.82 |
| old_thin | 2.0607 | 2.0663 | +0.0056 | $94,095.03 | $94,350.57 | $+255.54 |

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
