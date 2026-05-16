# exp-20260515-048 Space source-diversity authority-no-company trend risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need a different default-off allocation when the source-diversity profile has authoritative non-company source support.

## Single Changed Variable
`space_source_diversity_authority_no_company_trend_scalar` on top of accepted `exp-20260515-044`.

## Gate 1 Baseline
- before experiment: `exp-20260515-044` / `space_source_diversity_peer_nonleader_near_perfect_trend_risk`
- aggregate before EV: `26.5438`
- aggregate before PnL: `733923.08`

## Gate 2 Field Check
- open position field check passed: `True`
- source profile field check passed: `True`
- excluded source type: `company_release`
- authority source types: `['official_government_release', 'official_or_primary_release', 'official_regulatory_release']`
- target tickers: `['ASTS', 'BKSY', 'LUNR', 'PL', 'RDW']`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.444200 | 8.444200 | 0.000000 | 0.00 | 0.000000 | 18 | 18 |
| mid_weak | 16.530200 | 17.356500 | 0.826300 | 16305.00 | -0.000300 | 24 | 24 |
| old_thin | 1.569400 | 1.569400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.075`
- eligible signals: `3`
- adjusted signals: `3`
- adjusted counts: `{'space_source_diversity_authority_no_company_trend_risk_changed_ASTS': 2, 'space_source_diversity_authority_no_company_trend_risk_changed_LUNR': 1, 'space_source_diversity_authority_no_company_trend_risk_changed_signal': 3, 'space_source_diversity_authority_no_company_trend_risk_eligible_ASTS': 2, 'space_source_diversity_authority_no_company_trend_risk_eligible_LUNR': 1, 'space_source_diversity_authority_no_company_trend_risk_eligible_signal': 3}`
- aggregate EV delta: `0.8263`
- aggregate PnL delta: `16305.0`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'mid_weak': 0.8263}`
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
