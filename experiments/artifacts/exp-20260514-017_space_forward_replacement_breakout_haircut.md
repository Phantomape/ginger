# exp-20260514-017 Space forward replacement breakout haircut

## Hypothesis
Exp-20260514-009 showed the forward same-theme replacement-strength edge was strongest as a trend continuation helper. On top of accepted exp-20260514-009, this tests whether the same bucket should haircut breakout_long signals that may carry more tail noise without adding noisy tickers, broad filters, LLM authority, lifecycle rules, or live Space slots.

## Single Changed Variable
`space_forward_replacement_breakout_haircut_scalar` for `breakout_long` signals already in the accepted forward same-theme replacement-strength bucket. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-009 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `0.75`
- Aggregate delta vs exp-009: EV `0.134200`, PnL `-13487.96`
- Breakout-strength signals changed: `5` of `5` eligible
- Target tickers: `RKLB`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 1 |
| mid_weak | 0.637600 | 7498.22 | -0.008100 | 23 | 0.653300 | 1 |
| old_thin | -0.503400 | -20986.18 | -0.024800 | 25 | 0.733300 | 3 |

## Gate Checks
- Gate 2 passed: `True`
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
