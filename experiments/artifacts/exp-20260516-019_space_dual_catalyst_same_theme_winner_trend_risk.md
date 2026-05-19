# exp-20260516-019 Space dual-catalyst same-theme winner trend risk

## Hypothesis
Accepted dual-catalyst source-diverse official Space trend signals may still be under-sized when closed defense-budget government_space_contract rows also prove positive same-theme replacement value.

## Single Changed Variable
`space_dual_catalyst_same_theme_winner_trend_scalar` on top of accepted `exp-20260516-015`.

## Gate 1 Baseline
- before experiment: `exp-20260516-015` / `space_dual_catalyst_iwm_leader_trend_risk`
- aggregate before EV: `28.5324`
- aggregate before PnL: `735494.93`
- aggregate before max drawdown pct max: `0.2266`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- same-theme winner gate passed: `True`
- target tickers: `['BKSY', 'LUNR', 'RDW', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.546100 | 8.586000 | 0.039900 | 1795.60 | 0.002600 | 18 | 18 |
| mid_weak | 18.381400 | 18.483600 | 0.102200 | 3159.30 | 0.000100 | 23 | 23 |
| old_thin | 1.604900 | 1.604900 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0125`
- eligible signals: `4`
- changed signals: `4`
- changed tickers: `['LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta: `0.1421`
- aggregate PnL delta: `4954.9`
- max drawdown pct max delta: `0.0026`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0399, 'mid_weak': 0.1022}`
- regressed windows: `{}`

## Production Impact
```text
production_impact:
  shared_policy_changed: true
  backtester_adapter_changed: true
  run_adapter_changed: true
  replay_only: false
  parity_test_added: true
  live_slots: 0
```
