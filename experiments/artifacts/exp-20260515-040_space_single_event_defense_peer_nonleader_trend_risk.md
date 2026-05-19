# exp-20260515-040 Space single-event defense peer-nonleader trend risk

## Hypothesis
Single-event defense-only official Space `trend_long` signals may need a different default-off allocation when the ticker is still a Space peer nonleader.

## Single Changed Variable
`space_single_event_defense_peer_nonleader_trend_scalar` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `26.4644`
- aggregate before PnL: `730466.28`
- aggregate before max drawdown pct max: `0.2147`

## Gate 2 Field Check
- open position field check passed: `True`
- single-event defense gate passed: `True`
- target tickers: `['BKSY', 'PL', 'RDW']`
- target peer state: `nonleader`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.375200 | 8.375200 | 0.000000 | 0.00 | 0.000000 | 18 | 18 |
| mid_weak | 16.519800 | 16.519800 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0`
- eligible signals: `1`
- adjusted signals: `0`
- adjusted counts: `{'space_single_event_defense_peer_nonleader_trend_risk_eligible_BKSY': 1, 'space_single_event_defense_peer_nonleader_trend_risk_eligible_signal': 1}`
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
