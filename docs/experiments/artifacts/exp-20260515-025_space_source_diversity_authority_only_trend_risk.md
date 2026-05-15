# exp-20260515-025 Space source-diversity authority-only trend risk

## Hypothesis
Source-diverse official Space `trend_long` signals may need a different default-off allocation when all source types are government/regulatory/primary authority sources and the profile does not include a company release.

## Single Changed Variable
`space_source_diversity_authority_only_trend_scalar` on top of accepted `exp-20260515-024`.

## Gate 1 Baseline
- before experiment: `exp-20260515-024` / `space_source_diversity_peer_nonleader_trend_risk`
- aggregate before EV: `25.1824`
- aggregate before PnL: `672412.69`
- aggregate before max drawdown pct max: `0.1779`

## Gate 2 Field Check
- open position field check passed: `True`
- authority source types: `['official_government_release', 'official_or_primary_release', 'official_regulatory_release']`
- excluded source types: `['company_release']`

## Gate 3 Survival Audit
- min survival before: `0.64`
- min survival after: `0.64`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.379500 | 8.379500 | 0.000000 | 0.00 | 0.000000 | 20 | 20 |
| mid_weak | 13.726300 | 14.392400 | 0.666100 | 12903.59 | 0.000100 | 24 | 24 |
| old_thin | 3.076600 | 3.076600 | 0.000000 | 0.00 | 0.000000 | 24 | 24 |

## Best Variant
- scalar: `1.075`
- eligible signals: `3`
- adjusted signals: `3`
- skipped source-profile signals: `3`
- adjusted counts: `{'space_source_diversity_authority_only_trend_risk_changed_ASTS': 2, 'space_source_diversity_authority_only_trend_risk_changed_LUNR': 1, 'space_source_diversity_authority_only_trend_risk_changed_signal': 3, 'space_source_diversity_authority_only_trend_risk_eligible_ASTS': 2, 'space_source_diversity_authority_only_trend_risk_eligible_LUNR': 1, 'space_source_diversity_authority_only_trend_risk_eligible_signal': 3, 'space_source_diversity_authority_only_trend_risk_skipped_source_profile': 3, 'space_source_diversity_authority_only_trend_risk_skipped_source_profile_RKLB': 3}`
- aggregate EV delta: `0.6661`
- aggregate PnL delta: `12903.59`
- max drawdown pct max delta: `0.0`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'mid_weak': 0.6661}`
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
