# exp-20260516-018 space_dual_catalyst_peer_nonleader_trend_risk

## Hypothesis
Accepted dual-catalyst source-diverse official Space trend signals may still be under-sized when peer momentum is nonleader, because the customer-plus-government catalyst stack can offset peer-relative lag.

## Single Changed Variable
`space_dual_catalyst_peer_nonleader_trend_scalar` on top of accepted `exp-20260516-015`.

## Gate 1 Baseline
- before experiment: `exp-20260516-015` / `space_dual_catalyst_iwm_leader_trend_risk`
- aggregate before EV: `28.8867`
- aggregate before PnL: `746047.71`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- target peer state: `nonleader`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.621000 | 8.621000 | 0.000000 | 0.00 | 0.000000 | 18 | 18 |
| mid_weak | 18.660800 | 18.660800 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 1.604900 | 1.604900 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `0.95`
- eligible signals: `4`
- changed signals: `4`
- changed tickers: `['ASTS', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- aggregate EV delta: `0.0`
- aggregate PnL delta: `0.0`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{}`
- regressed windows: `{}`

## Production Impact
```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
  live_slots: 0
```
