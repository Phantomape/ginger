# exp-20260515-037 Space GSAT connectivity candidate pool

## Hypothesis
GSAT may be a cleaner Space satellite-connectivity candidate-pool extension than rejected mature-satcom or theme-ETF admissions because it is registry-defined, event-guarded, non-live, has full frozen OHLCV coverage, and has official Golden Dome event evidence.

## Single Changed Variable
`space_gsat_connectivity_candidate_pool_membership` on top of accepted `exp-20260515-024`. Entries, exits, ranking, stops, LLM/news, and live Space slots stay fixed.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `26.4644`
- aggregate before PnL: `730466.28`
- aggregate before max drawdown pct max: `0.2147`

## Gate 2 Field Check
- open position field check passed: `True`
- GSAT candidate gate passed: `True`
- added tickers: `['GSAT']`
- failed candidate checks: `[]`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6066`
- no new filter was added; this is candidate membership under a registry/event/coverage gate.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | GSAT trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.375200 | 8.512400 | 0.137200 | 1217.66 | -0.005200 | 18 | 19 | 1 |
| mid_weak | 16.519800 | 16.474000 | -0.045800 | -1131.84 | 0.000000 | 24 | 24 | 0 |
| old_thin | 1.569400 | 1.148900 | -0.420500 | -16811.12 | -0.002400 | 23 | 23 | 0 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `-0.3291`
- aggregate PnL delta: `-16725.3`
- improved windows: `{'late_strong': 0.1372}`
- regressed windows: `{'mid_weak': -0.0458, 'old_thin': -0.4205}`
- GSAT trades: `1`

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
