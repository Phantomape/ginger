# exp-20260514-036 Space early-confirmation trend risk

## Hypothesis
Space official catalysts with immediate 5d cash and same-theme confirmation may deserve conservative trend risk allocation if the 10d same-theme replacement profile stays above the accepted $500 strength floor. This tests a fast-absorption timing cohort without adding tickers, LLM authority, or lifecycle changes.

## Single Changed Variable
`space_early_confirmation_trend_scalar` for official Space `trend_long` signals whose closed event-state profile has positive average 5d cash and same-theme reaction plus 10d same-theme value at or above the accepted $500 strength floor. Candidate pool, ranking, targets, stops, LLM/news, and accepted exp030 stack stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.0`
- Aggregate delta vs exp030: EV `0.000000`, PnL `0.00`
- Early-confirmation signals changed: `0` of `0` eligible
- Target tickers: `BKSY`

## Three-Window Deltas vs Exp030
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 23 | 0.653300 | 0 |
| old_thin | 0.000000 | 0.00 | 0.000000 | 25 | 0.706700 | 0 |

## Gate Checks
- Gate 2 passed: `False`
- Gate 3 survival passed: `True`

## Production Impact
```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
```
