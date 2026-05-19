# exp-20260516-024 Space dual-catalyst financing-profile trend risk

## Hypothesis
Accepted dual-catalyst source-diverse official Space trend signals may still be mis-sized when the production registry event_guard_profile contains financing or dilution sensitivity; the customer-plus-government catalyst stack may change the payoff distribution of that already accepted Space financing state.

## Single Changed Variable
`space_dual_catalyst_financing_profile_trend_scalar` on top of accepted `exp-20260516-023`.

## Gate 1 Baseline
- before experiment: `exp-20260516-023` / `space_dual_catalyst_near_perfect_trend_risk`
- aggregate before EV: `28.7691`
- aggregate before PnL: `742549.16`
- aggregate before max drawdown pct max: `0.2318`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- financing profile field check passed: `True`
- target tickers: `['ASTS', 'RKLB']`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.622700 | 8.664000 | 0.041300 | 1863.71 | 0.002500 | 18 | 18 |
| mid_weak | 18.541300 | 18.784700 | 0.243400 | 6290.61 | 0.000000 | 23 | 23 |
| old_thin | 1.605100 | 1.605100 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0125`
- eligible signals: `5`
- changed signals: `5`
- changed tickers: `['ASTS', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta: `0.2847`
- aggregate PnL delta: `8154.32`
- max drawdown pct max delta: `0.0025`

## Decision
- decision: `accept`
- Gate 4 passed: `True`
- improved windows: `{'late_strong': 0.0413, 'mid_weak': 0.2434}`
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
