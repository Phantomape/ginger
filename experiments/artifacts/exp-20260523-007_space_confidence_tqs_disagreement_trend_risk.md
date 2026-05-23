# exp-20260523-007 Space confidence/TQS disagreement trend risk

## Hypothesis
Within accepted dual-catalyst benchmark-breadth Space trend signals, high trade_quality_score with only moderate confidence_score may identify a catalyst/price-action setup that the generic signal confidence underweights. A bounded scalar on that disagreement bucket could improve EV without changing the candidate pool, LLM/news boundary, or live Space slots.

## Single Changed Variable
`space_confidence_tqs_disagreement_trend_risk_scalar` gated by high TQS and moderate confidence.

## Trial Accounting
- trial_family: `space_signal_quality_disagreement_allocation`
- changed_variable: `space_confidence_tqs_disagreement_trend_risk_scalar`
- prior_trial_count: `0` for this exact benchmark-breadth confidence/TQS interaction
- nearby_prior_experiments: `exp-20260512-008`, `exp-20260519-027`, `exp-20260520-020`, `exp-20260522-019`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `new_production_visible_signal_quality_interaction`

## Gate 1 Baseline
- current accepted experiment: `exp-20260519-027`
- current benchmark-breadth scalar: `1.021875`
- current aggregate EV: `29.0599`
- current aggregate PnL: `741041.42`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- benchmark-breadth field check passed: `True`
- signal field check passed: `True`
- candidate signals: `4`
- missing confidence_score: `0`
- missing trade_quality_score: `0`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.762700 | 8.978700 | 0.216000 | 11355.04 | 0.016000 | 17 | 17 |
| mid_weak | 19.058800 | 19.058800 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 1.238400 | 1.238400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.075`
- candidate signals: `4`
- eligible signals: `3`
- changed signals: `3`
- changed tickers: `['LUNR', 'RKLB']`
- changed windows: `['late_strong', 'mid_weak']`
- required EV delta for acceptance: `2.90599`
- aggregate EV delta vs current: `0.216`
- aggregate PnL delta vs current: `11355.04`
- max drawdown delta vs current: `0.016`

## Decision
- decision: `reject`
- Gate 4 passed: `False`
- improved windows: `{'late_strong': 0.216}`
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
