# exp-20260514-009 Space forward replacement trend-strength risk

## Hypothesis
On top of accepted exp-20260514-002, the forward same-theme replacement-strength Space edge may be stronger for trend_long continuation than for breakouts. A single extra trend-only scalar tests whether replacement-strength allocation should become more strategy-aware without changing the Space pool, rankings, targets, stops, LLM/news, or live slots.

## Single Changed Variable
`space_forward_replacement_trend_strength_scalar` for `trend_long` signals already in the accepted forward same-theme replacement-strength bucket. Candidate pool, event labels, ranking, targets, stops, LLM/news, accepted exp-002 stack, and live Space slots stay fixed.

## Gate 4 Summary
- Decision: `accepted`
- Best scalar: `1.05`
- Aggregate delta vs exp-002: EV `0.423800`, PnL `12670.90`
- Trend-strength signals changed: `7` of `7` eligible
- Target tickers: `BKSY, RDW, RKLB`

## Three-Window Deltas vs Exp-002
| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.069300 | 3788.47 | 0.006500 | 20 | 0.706900 | 1 |
| mid_weak | 0.221900 | 5305.59 | 0.000100 | 23 | 0.653300 | 4 |
| old_thin | 0.132600 | 3576.84 | 0.000100 | 25 | 0.733300 | 2 |

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
