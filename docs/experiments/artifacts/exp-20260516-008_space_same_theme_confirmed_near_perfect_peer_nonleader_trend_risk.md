# exp-20260516-008 Space same-theme-confirmed near-perfect peer-nonleader risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need an extra default-off allocation scalar when they are peer nonleaders, near-perfect by TQS, and also confirmed by a positive defense-budget same-theme winner forward profile.

## Single Changed Variable
`space_same_theme_confirmed_near_perfect_peer_nonleader_trend_scalar` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `26.5438`
- aggregate before PnL: `733923.08`
- aggregate before max drawdown pct max: `0.2196`

## Gate 2 Field Check
- open position field check passed: `True`
- same-theme winner gate passed: `True`
- target same-theme winner tickers: `['BKSY', 'LUNR', 'RDW', 'RKLB']`
- target TQS: `0.95 <= TQS < 1.0`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.444200 | 8.569700 | 0.125500 | 6840.24 | 0.010000 | 18 | 18 |
| mid_weak | 16.530200 | 16.530200 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.05`
- eligible signals: `2`
- adjusted signals: `2`
- adjusted counts: `{'space_same_theme_confirmed_near_perfect_peer_nonleader_trend_risk_changed_RKLB': 2, 'space_same_theme_confirmed_near_perfect_peer_nonleader_trend_risk_changed_signal': 2, 'space_same_theme_confirmed_near_perfect_peer_nonleader_trend_risk_eligible_RKLB': 2, 'space_same_theme_confirmed_near_perfect_peer_nonleader_trend_risk_eligible_signal': 2}`
- aggregate EV delta: `0.1255`
- aggregate PnL delta: `6840.24`
- max drawdown pct max delta: `0.01`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'late_strong': 0.1255}`
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
