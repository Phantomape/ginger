# exp-20260514-024 Space forward replacement IWM-leader trend risk

## Hypothesis
Space replacement-strength allocation may be strongest when forward same-theme cash evidence, trend continuation, and smallcap tape leadership agree. On top of accepted exp-20260514-009, a single extra IWM-leader trend scalar tests the playbook's catalyst/source/tape interaction direction without adding noisy tickers, broad filters, LLM authority, lifecycle rules, or live Space slots.

## Single Changed Variable
`space_forward_replacement_iwm_leader_trend_scalar` for `trend_long` signals already in the accepted forward same-theme replacement-strength bucket and whose IWM relative momentum state is `smallcap_leader`. Candidate pool, ranking, targets, stops, LLM/news, accepted exp-009 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.025`
- Aggregate delta vs exp-009: EV `0.228200`, PnL `6852.85`
- IWM-leader trend signals changed: `7` of `7` eligible
- Target tickers: `BKSY, RDW, RKLB`

## Three-Window Deltas vs Exp-009
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.044900 | 1960.39 | 0.003400 | 20 | 0.706900 | 1 |
| mid_weak | 0.113500 | 3012.34 | 0.000200 | 23 | 0.653300 | 4 |
| old_thin | 0.069800 | 1880.12 | 0.000000 | 25 | 0.720000 | 2 |

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
