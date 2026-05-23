# exp-20260523-006 Broad-Market Max-Daily-Return Support Notional

Decision: `rejected_broad_market_max_daily_return_notional`.

Single causal variable: 20-day max daily return cap for default-off broad-market paper notional support.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_max_daily_return_support | FAIL | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% | 13.52% | 42.72% |
| maxday20_lte_0p08_scalar_1p025 | FAIL | 41 | +0.0078 | +0.05% | $+228.02 | 3 | 0 | +0.0000% | 13.43% | 42.43% |
| maxday20_lte_0p08_scalar_1p05 | FAIL | 41 | +0.0157 | +0.09% | $+455.91 | 3 | 0 | +0.0000% | 13.34% | 42.14% |
| maxday20_lte_0p08_scalar_1p075 | FAIL | 41 | +0.0236 | +0.14% | $+683.78 | 3 | 0 | +0.0000% | 13.25% | 41.86% |
| maxday20_lte_0p08_scalar_1p1 | FAIL | 41 | +0.0314 | +0.19% | $+911.83 | 3 | 0 | +0.0000% | 13.16% | 41.58% |
| maxday20_lte_0p08_scalar_1p15 | FAIL | 41 | +0.0312 | +0.19% | $+1,367.74 | 2 | 1 | +0.0100% | 12.99% | 41.03% |
| maxday20_lte_0p09_scalar_1p025 | FAIL | 48 | +0.0398 | +0.24% | $+574.54 | 3 | 0 | +0.0100% | 13.35% | 42.59% |
| maxday20_lte_0p09_scalar_1p05 | FAIL | 48 | +0.0637 | +0.38% | $+1,148.94 | 3 | 0 | +0.0200% | 13.19% | 42.47% |
| maxday20_lte_0p09_scalar_1p075 | FAIL | 48 | +0.0875 | +0.52% | $+1,723.31 | 3 | 0 | +0.0300% | 13.03% | 42.35% |
| maxday20_lte_0p09_scalar_1p1 | FAIL | 48 | +0.1275 | +0.76% | $+2,297.87 | 3 | 0 | +0.0400% | 12.87% | 42.23% |
| maxday20_lte_0p09_scalar_1p15 | FAIL | 48 | +0.1752 | +1.04% | $+3,446.82 | 3 | 0 | +0.0500% | 12.57% | 42.01% |
| maxday20_lte_0p10_scalar_1p025 | FAIL | 51 | +0.0405 | +0.24% | $+575.32 | 3 | 0 | +0.0100% | 13.34% | 42.56% |
| maxday20_lte_0p10_scalar_1p05 | FAIL | 51 | +0.0650 | +0.39% | $+1,150.49 | 3 | 0 | +0.0100% | 13.17% | 42.41% |
| maxday20_lte_0p10_scalar_1p075 | FAIL | 51 | +0.0895 | +0.53% | $+1,725.64 | 3 | 0 | +0.0200% | 13.00% | 42.26% |
| maxday20_lte_0p10_scalar_1p1 | FAIL | 51 | +0.1302 | +0.77% | $+2,300.99 | 3 | 0 | +0.0300% | 12.83% | 42.12% |
| maxday20_lte_0p10_scalar_1p15 | FAIL | 51 | +0.1794 | +1.07% | $+3,451.49 | 3 | 0 | +0.0500% | 12.51% | 41.84% |
| maxday20_lte_0p11_scalar_1p025 | FAIL | 54 | +0.0238 | +0.14% | $+557.75 | 3 | 0 | +0.0100% | 13.34% | 42.55% |
| maxday20_lte_0p11_scalar_1p05 | FAIL | 54 | +0.0477 | +0.28% | $+1,115.34 | 3 | 0 | +0.0100% | 13.16% | 42.39% |
| maxday20_lte_0p11_scalar_1p075 | FAIL | 54 | +0.0715 | +0.42% | $+1,672.90 | 3 | 0 | +0.0200% | 12.99% | 42.23% |
| maxday20_lte_0p11_scalar_1p1 | FAIL | 54 | +0.1116 | +0.66% | $+2,230.67 | 3 | 0 | +0.0300% | 12.82% | 42.07% |
| maxday20_lte_0p11_scalar_1p15 | FAIL | 54 | +0.1593 | +0.95% | $+3,346.02 | 3 | 0 | +0.0500% | 12.49% | 41.77% |
| maxday20_lte_0p12_scalar_1p025 | FAIL | 60 | +0.0235 | +0.14% | $+534.56 | 3 | 0 | +0.0000% | 13.33% | 42.52% |
| maxday20_lte_0p12_scalar_1p05 | FAIL | 60 | +0.0374 | +0.22% | $+1,068.96 | 2 | 1 | +0.0100% | 13.14% | 42.33% |
| maxday20_lte_0p12_scalar_1p075 | FAIL | 60 | +0.0610 | +0.36% | $+1,603.32 | 2 | 1 | +0.0100% | 12.96% | 42.14% |
| maxday20_lte_0p12_scalar_1p1 | FAIL | 60 | +0.0844 | +0.50% | $+2,137.90 | 2 | 1 | +0.0100% | 12.79% | 41.96% |
| maxday20_lte_0p12_scalar_1p15 | FAIL | 60 | +0.1477 | +0.88% | $+3,206.85 | 2 | 1 | +0.0300% | 12.45% | 41.62% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4819 | +0.0629 | $159,891.81 | $160,900.49 | $+1,008.68 |
| mid_weak | 7.3451 | 7.4508 | +0.1057 | $160,023.22 | $161,974.20 | $+1,950.98 |
| old_thin | 2.0757 | 2.0865 | +0.0108 | $94,782.99 | $95,274.82 | $+491.83 |

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
