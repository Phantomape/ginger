# exp-20260522-019 Space forward-consistency trend risk

## Hypothesis
Within source-diverse dual-catalyst Space trend signals, closed forward rows that show multi-event, all-benchmark positive consistency should represent higher-quality catalyst continuation than average-only replacement strength; a small risk scalar could improve EV without changing the candidate pool or production/LLM boundaries.

## Single Changed Variable
`space_forward_consistency_trend_risk_scalar` gated by closed 10d forward profile consistency.

## Trial Accounting
- trial_family: `space_forward_replacement_consistency`
- changed_variable: `space_forward_consistency_trend_risk_scalar`
- prior_trial_count: `0` for this exact row-level consistency field
- nearby_prior_experiments: `exp-20260514-047`, `exp-20260519-027`, `exp-20260521-017`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `new_production_visible_field`

## Gate 1 Baseline
- current accepted experiment: `exp-20260519-027`
- current benchmark-breadth scalar: `1.021875`
- current aggregate EV: `29.0599`
- current aggregate PnL: `741041.42`

## Gate 2 Field Check
- open position field check passed: `True`
- dual catalyst profile field check passed: `True`
- forward profile field check passed: `True`
- signal field check passed: `True`
- target tickers: `['LUNR']`
- candidate signals: `6`
- missing profile signals: `0`

## Gate 3 Survival Audit
- min survival before: `0.6267`
- min survival after: `0.6267`
- no filter was added; this is a sizing-only scalar.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 8.762700 | 8.762700 | 0.000000 | 0.00 | 0.000000 | 17 | 17 |
| mid_weak | 19.058800 | 19.058800 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |
| old_thin | 1.238400 | 1.238400 | 0.000000 | 0.00 | 0.000000 | 23 | 23 |

## Best Variant
- scalar: `1.0125`
- candidate signals: `6`
- eligible signals: `1`
- changed signals: `1`
- changed tickers: `['LUNR']`
- changed windows: `['mid_weak']`
- required EV delta for acceptance: `2.90599`
- aggregate EV delta vs current: `0.0`
- aggregate PnL delta vs current: `0.0`
- max drawdown delta vs current: `0.0`

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
