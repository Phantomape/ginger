# exp-20260514-026 Space forward replacement company-source trend risk

## Hypothesis
Space replacement-strength allocation should be strongest when closed 10d same-theme replacement value, trend continuation, and a company-release customer-win catalyst all agree. On top of accepted exp-20260514-024, a single extra company-source trend scalar tests that catalyst-quality interaction without adding tickers, broad filters, LLM authority, lifecycle rules, or live Space slots.

## Single Changed Variable
`space_forward_replacement_company_source_trend_scalar` for `trend_long` signals already in the accepted forward same-theme replacement-strength bucket and whose event seed profile has a `company_release` customer-win source. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-024 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp-024: EV `0.162400`, PnL `4879.91`
- Company-source trend signals changed: `3` of `3` eligible
- Target tickers: `RKLB`

## Three-Window Deltas vs Exp-024
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.028600 | 2041.54 | 0.003500 | 20 | 0.706900 | 1 |
| mid_weak | 0.133800 | 2838.37 | 0.000000 | 23 | 0.653300 | 2 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.720000 | 0 |

## Gate Checks
- Gate 2 passed: `True`
- Gate 3 survival passed: `True`

## Production Impact
```text
production_impact:
  shared_policy_changed: True
  backtester_adapter_changed: False
  run_adapter_changed: True
  replay_only: True
  parity_test_added: True
```
