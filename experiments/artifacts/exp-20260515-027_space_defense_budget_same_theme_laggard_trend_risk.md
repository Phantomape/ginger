# exp-20260515-027 Space defense-budget same-theme laggard trend risk

## Hypothesis
Official Space `trend_long` signals tied to defense-budget government-contract events may be over-sized when their mature 10d profile is positive versus cash but nonpositive versus the same-theme replacement basket.

## Single Changed Variable
`space_defense_budget_same_theme_laggard_trend_scalar` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `24.514`
- aggregate before PnL: `662636.78`
- aggregate before max drawdown pct max: `0.2025`

## Gate 2 Field Check
- open position field check passed: `True`
- defense-budget same-theme laggard gate passed: `True`
- target tickers: `['ASTS', 'PL']`
- target profile rows: `2`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.132100 | 8.132100 | 0.000000 | 0.00 | 0.000000 | 18 | 18 |
| mid_weak | 15.316000 | 15.316000 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |
| old_thin | 1.065900 | 1.065900 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0`
- eligible signals: `0`
- adjusted signals: `0`
- target profile rows: `2`
- adjusted counts: `{}`
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
