# exp-20260515-019 Space theme-beta candidate pool

## Hypothesis
Existing Space theme-beta benchmark ETFs ARKX/UFO may be a cleaner candidate-pool extension than another small operating Space ticker: lower idiosyncratic risk, full frozen OHLCV coverage, and direct same-theme replacement relevance.

## Single Changed Variable
`space_theme_beta_candidate_pool_membership` on top of accepted `exp-20260514-053`. Entries, exits, ranking, stops, LLM/news, and live Space slots stay fixed.

## Gate 1 Baseline
- before experiment: `exp-20260514-053` / `space_benchmark_breadth_iwm_leader_trend_risk`
- aggregate before EV: `24.6984`
- aggregate before PnL: `652524.4`
- aggregate before max drawdown pct max: `0.1703`

## Gate 2 Field Check
- open position field check passed: `True`
- theme-beta candidate gate passed: `True`
- added tickers: `['ARKX', 'UFO']`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.5761`
- no new filter was added; this is candidate membership under a registry/OHLCV gate.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.219100 | 7.784500 | -0.434600 | 10225.96 | 0.024200 | 20 | 20 | 2 |
| mid_weak | 13.402700 | 5.730700 | -7.672000 | -118379.83 | 0.006500 | 24 | 26 | 4 |
| old_thin | 3.076600 | 2.138400 | -0.938200 | -21136.94 | 0.001600 | 24 | 28 | 5 |

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `-9.0448`
- aggregate PnL delta: `-129290.81`
- improved windows: `{}`
- regressed windows: `{'late_strong': -0.4346, 'mid_weak': -7.672, 'old_thin': -0.9382}`
- extension trades: `11`

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
