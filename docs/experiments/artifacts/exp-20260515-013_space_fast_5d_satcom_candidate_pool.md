# exp-20260515-013 Space fast-5d satcom candidate pool

## Hypothesis
Mature satcom tickers with all-positive 5d forward confirmation may be a cleaner Space candidate-pool extension than the rejected broad IRDM/VSAT/SATS satcom breadth test.

## Single Changed Variable
`space_fast_5d_satcom_candidate_pool_membership` on top of accepted `exp-20260514-053`. Entries, exits, ranking, stops, LLM/news, and live Space slots stay fixed.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `28.1981`
- aggregate before PnL: `701204.54`
- aggregate before max drawdown pct max: `0.1616`

## Gate 2 Field Check
- open position field check passed: `True`
- satcom fast-5d gate passed: `True`
- added tickers: `['IRDM', 'VSAT']`

## Gate 3 Survival Audit
- min survival before: `0.6533`
- min survival after: `0.6623`
- no new filter was added; this is candidate membership under a forward-evidence gate.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.161100 | 8.691100 | 0.530000 | 19713.24 | 0.023900 | 20 | 24 | 3 |
| mid_weak | 15.165500 | 18.771400 | 3.605900 | 57644.70 | -0.000400 | 23 | 24 | 1 |
| old_thin | 4.871500 | 4.596300 | -0.275200 | -5575.94 | 0.000900 | 25 | 25 | 0 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `3.8607`
- aggregate PnL delta: `71782.0`
- improved windows: `{'late_strong': 0.53, 'mid_weak': 3.6059}`
- regressed windows: `{'old_thin': -0.2752}`
- extension trades: `4`

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
