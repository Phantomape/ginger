# exp-20260520-004 Broad-Market Trend-Persistence Notional

Decision: `accepted_default_off_broad_market_trend_persistence_notional`.

Single causal variable: 20-day positive close-to-close day ratio paper-notional support on the fixed exp-20260520-003 broad-market paper sleeve.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_trend_persistence | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | +0.0000% | 13.25% | 43.28% |
| posday20_gte_0p55_scalar_1p025 | PASS | 79 | +0.0253 | $+583.72 | 3 | 0 | +0.0100% | 13.30% | 43.18% |
| posday20_gte_0p55_scalar_1p05 | PASS | 79 | +0.0505 | $+1,167.43 | 3 | 0 | +0.0200% | 13.35% | 43.08% |
| posday20_gte_0p55_scalar_1p075 | PASS | 79 | +0.0599 | $+1,751.14 | 3 | 0 | +0.0300% | 13.39% | 42.98% |
| posday20_gte_0p55_scalar_1p1 | PASS | 79 | +0.0852 | $+2,334.87 | 3 | 0 | +0.0400% | 13.44% | 42.89% |
| posday20_gte_0p55_scalar_1p15 | PASS | 79 | +0.1197 | $+3,502.29 | 3 | 0 | +0.0500% | 13.52% | 42.72% |
| posday20_gte_0p60_scalar_1p025 | PASS | 66 | +0.0105 | $+227.78 | 3 | 0 | +0.0100% | 13.06% | 43.00% |
| posday20_gte_0p60_scalar_1p05 | FAIL | 66 | +0.0050 | $+455.56 | 2 | 1 | +0.0100% | 12.89% | 42.73% |
| posday20_gte_0p60_scalar_1p075 | FAIL | 66 | +0.0154 | $+683.34 | 2 | 1 | +0.0200% | 12.71% | 42.47% |
| posday20_gte_0p60_scalar_1p1 | FAIL | 66 | +0.0005 | $+911.12 | 1 | 2 | +0.0200% | 12.55% | 42.21% |
| posday20_gte_0p60_scalar_1p15 | FAIL | 66 | +0.0054 | $+1,366.69 | 1 | 2 | +0.0300% | 12.22% | 41.71% |
| posday20_gte_0p65_scalar_1p025 | PASS | 56 | +0.0047 | $+113.49 | 3 | 0 | +0.0100% | 13.11% | 42.98% |
| posday20_gte_0p65_scalar_1p05 | FAIL | 56 | -0.0065 | $+226.97 | 2 | 1 | +0.0100% | 12.97% | 42.68% |
| posday20_gte_0p65_scalar_1p075 | FAIL | 56 | -0.0020 | $+340.46 | 2 | 1 | +0.0100% | 12.84% | 42.40% |
| posday20_gte_0p65_scalar_1p1 | FAIL | 56 | +0.0028 | $+453.94 | 2 | 1 | +0.0100% | 12.71% | 42.11% |
| posday20_gte_0p65_scalar_1p15 | FAIL | 56 | -0.0133 | $+680.91 | 1 | 2 | +0.0200% | 12.45% | 41.56% |
| posday20_gte_0p70_scalar_1p025 | FAIL | 37 | -0.0011 | $-46.83 | 1 | 2 | +0.0200% | 13.17% | 43.18% |
| posday20_gte_0p70_scalar_1p05 | FAIL | 37 | -0.0021 | $-93.66 | 1 | 2 | +0.0500% | 13.09% | 43.07% |
| posday20_gte_0p70_scalar_1p075 | FAIL | 37 | -0.0283 | $-140.48 | 0 | 3 | +0.0700% | 13.01% | 42.97% |
| posday20_gte_0p70_scalar_1p1 | FAIL | 37 | -0.0453 | $-187.32 | 0 | 3 | +0.0900% | 12.93% | 42.87% |
| posday20_gte_0p70_scalar_1p15 | FAIL | 37 | -0.0474 | $-280.98 | 0 | 3 | +0.1300% | 12.78% | 42.67% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.3402 | 7.4190 | +0.0788 | $157,853.12 | $159,891.81 | $+2,038.69 |
| mid_weak | 7.3136 | 7.3451 | +0.0315 | $158,992.04 | $160,023.22 | $+1,031.18 |
| old_thin | 2.0663 | 2.0757 | +0.0094 | $94,350.57 | $94,782.99 | $+432.42 |

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
