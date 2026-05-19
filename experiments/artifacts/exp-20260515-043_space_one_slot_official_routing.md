# exp-20260515-043 Space one-slot official routing

## Hypothesis
Default-off Space exposure may be over-allocated on days with multiple official Space candidates. Allowing only the top already-ranked official Space signal per sizing batch may improve replacement value and tail behavior without adding tickers or new LLM/rule fields.

## Single Changed Variable
`space_official_daily_sizing_slots` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `26.4644`
- aggregate before PnL: `730466.28`
- aggregate before max drawdown pct max: `0.2147`

## Gate 2 Field Check
- open position field check passed: `True`
- official Space tickers: `['ASTS', 'BKSY', 'LUNR', 'PL', 'RDW', 'RKLB']`
- no new prompt field, news field, LLM field, price field, or threshold is required.

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.6552`
- this is Space sleeve capacity/routing, not a new entry filter.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.375200 | 8.375200 | 0.000000 | 0.00 | 0.000000 | 18 | 18 |
| mid_weak | 16.519800 | 5.742800 | -10.777000 | -249169.13 | -0.067900 | 24 | 22 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Routing Coverage
- kept official Space signals: `20`
- filtered official Space signals: `4`
- routing counts: `{'filtered_ASTS': 1, 'filtered_LUNR': 1, 'filtered_RKLB': 2, 'filtered_official_space_signal': 4, 'kept_ASTS': 5, 'kept_BKSY': 2, 'kept_LUNR': 1, 'kept_PL': 5, 'kept_RDW': 3, 'kept_RKLB': 4, 'kept_official_space_signal': 20, 'official_space_batch_size_1': 16, 'official_space_batch_size_2': 4, 'official_space_signals_seen': 24, 'sizing_batches_with_official_space_signal': 20}`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- aggregate EV delta: `-10.777`
- aggregate PnL delta: `-249169.13`
- max drawdown pct max delta: `0.0`
- improved windows: `{}`
- regressed windows: `{'mid_weak': -10.777}`

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
