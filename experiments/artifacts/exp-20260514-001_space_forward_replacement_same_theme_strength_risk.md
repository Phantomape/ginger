# exp-20260514-001 Space forward replacement same-theme strength risk

## Hypothesis
On top of accepted exp-20260513-113, official Space signals whose closed 10d forward event-state profile has stronger same-theme replacement value may deserve incremental default-off risk. This tests the playbook's forward replacement-value direction without LLM soft-ranking, ticker expansion, or live Space slots.

## Single Changed Variable
`space_forward_replacement_same_theme_strength_scalar` for the narrower closed-forward profile bucket whose average 10d same-theme replacement value clears the tested floor. Candidate pool, event labels, ranking, targets, stops, LLM/news, accepted exp-113 scalar, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best floor/scalar: `500.0` / `1.05`
- Aggregate delta vs exp-113: EV `0.417400`, PnL `15070.38`
- Same-theme-strength signals changed: `12` of `12` eligible
- Target tickers: `BKSY, RDW, RKLB`
- Target set narrowed vs exp-113: `True`

## Three-Window Deltas vs Exp-113
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.086300 | 3684.09 | 0.006100 | 20 | 0.706900 | 2 |
| mid_weak | 0.106900 | 3974.75 | 0.003900 | 23 | 0.653300 | 5 |
| old_thin | 0.224200 | 7411.54 | 0.004900 | 25 | 0.733300 | 5 |

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
