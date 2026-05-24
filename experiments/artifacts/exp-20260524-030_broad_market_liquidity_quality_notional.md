# exp-20260524-030 Broad-Market Liquidity-Quality Notional

Decision: `rejected_broad_market_liquidity_quality_notional`.

Single causal variable: 20-day average dollar-volume liquidity tier paper-notional scalar on the accepted broad-market paper sleeve.

## Sweep

| Variant | Mode | Gate 4 | Adjusted | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |
|---|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_liquidity_quality_scalar | none | FAIL | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% |
| deep_liquidity_gte_500m_scalar_1p025 | support_deep_liquidity | FAIL | 20 | +0.0135 | +0.08% | $+126.18 | 2 | 1 | +0.0100% |
| deep_liquidity_gte_500m_scalar_1p05 | support_deep_liquidity | FAIL | 20 | +0.0044 | +0.03% | $+252.30 | 1 | 2 | +0.0100% |
| deep_liquidity_gte_500m_scalar_1p075 | support_deep_liquidity | FAIL | 20 | +0.0113 | +0.07% | $+378.39 | 1 | 2 | +0.0200% |
| deep_liquidity_gte_500m_scalar_1p1 | support_deep_liquidity | FAIL | 20 | +0.0182 | +0.11% | $+504.57 | 1 | 2 | +0.0200% |
| deep_liquidity_gte_500m_scalar_1p15 | support_deep_liquidity | FAIL | 20 | +0.0226 | +0.13% | $+756.88 | 2 | 1 | +0.0600% |
| deep_liquidity_gte_1000m_scalar_1p025 | support_deep_liquidity | FAIL | 6 | +0.0102 | +0.06% | $+39.87 | 1 | 1 | +0.0100% |
| deep_liquidity_gte_1000m_scalar_1p05 | support_deep_liquidity | FAIL | 6 | +0.0140 | +0.08% | $+79.73 | 1 | 1 | +0.0200% |
| deep_liquidity_gte_1000m_scalar_1p075 | support_deep_liquidity | FAIL | 6 | +0.0177 | +0.11% | $+119.57 | 1 | 1 | +0.0200% |
| deep_liquidity_gte_1000m_scalar_1p1 | support_deep_liquidity | FAIL | 6 | +0.0215 | +0.13% | $+159.43 | 1 | 1 | +0.0300% |
| deep_liquidity_gte_1000m_scalar_1p15 | support_deep_liquidity | FAIL | 6 | +0.0355 | +0.21% | $+239.16 | 1 | 1 | +0.0400% |
| deep_liquidity_gte_2000m_scalar_1p025 | support_deep_liquidity | FAIL | 2 | -0.0110 | -0.07% | $-71.37 | 0 | 1 | +0.0100% |
| deep_liquidity_gte_2000m_scalar_1p05 | support_deep_liquidity | FAIL | 2 | -0.0125 | -0.07% | $-142.75 | 0 | 1 | +0.0200% |
| deep_liquidity_gte_2000m_scalar_1p075 | support_deep_liquidity | FAIL | 2 | -0.0141 | -0.08% | $-214.13 | 0 | 1 | +0.0200% |
| deep_liquidity_gte_2000m_scalar_1p1 | support_deep_liquidity | FAIL | 2 | -0.0157 | -0.09% | $-285.50 | 0 | 1 | +0.0300% |
| deep_liquidity_gte_2000m_scalar_1p15 | support_deep_liquidity | FAIL | 2 | -0.0282 | -0.17% | $-428.25 | 0 | 1 | +0.0400% |
| thin_liquidity_lt_250m_scalar_0p85 | haircut_thin_liquidity | FAIL | 57 | -0.0430 | -0.26% | $-2,777.91 | 1 | 2 | +0.2400% |
| thin_liquidity_lt_250m_scalar_0p90 | haircut_thin_liquidity | FAIL | 57 | -0.0309 | -0.18% | $-1,851.95 | 1 | 2 | +0.1600% |
| thin_liquidity_lt_250m_scalar_0p95 | haircut_thin_liquidity | FAIL | 57 | -0.0281 | -0.17% | $-925.98 | 1 | 2 | +0.0800% |
| thin_liquidity_lt_500m_scalar_0p85 | haircut_thin_liquidity | FAIL | 70 | -0.1058 | -0.63% | $-3,589.47 | 1 | 2 | +0.2400% |
| thin_liquidity_lt_500m_scalar_0p90 | haircut_thin_liquidity | FAIL | 70 | -0.0578 | -0.34% | $-2,393.00 | 1 | 2 | +0.1600% |
| thin_liquidity_lt_500m_scalar_0p95 | haircut_thin_liquidity | FAIL | 70 | -0.0255 | -0.15% | $-1,196.50 | 1 | 2 | +0.0800% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4833 | +0.0643 | $159,891.81 | $160,585.57 | $+693.76 |
| mid_weak | 7.3451 | 7.3451 | +0.0000 | $160,023.22 | $160,023.22 | $+0.00 |
| old_thin | 2.0757 | 2.0469 | -0.0288 | $94,782.99 | $94,328.39 | $-454.60 |

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
