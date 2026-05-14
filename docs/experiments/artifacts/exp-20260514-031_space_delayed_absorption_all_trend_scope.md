# exp-20260514-031 Space delayed-absorption all-trend scope

Decision: `rejected_space_delayed_absorption_all_trend_scope`.

Single variable: broaden the delayed-absorption `trend_long` scope from the exp030 source-diverse moved subset to every delayed-profile Space `trend_long` candidate. The scalar remains 1.025x; entries, exits, ranking, targets, LLM/news, ticker breadth, and live slots stay fixed.

## Three-Window Delta vs Exp030
| window | EV delta | PnL delta | max DD delta | survival | new-scope adjusted |
|---|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 0.706900 | 0 |
| mid_weak | 0.000000 | 0.00 | 0.000000 | 0.653300 | 0 |
| old_thin | 0.072400 | 1961.44 | 0.000100 | 0.706700 | 2 |

Aggregate EV delta: `0.072400`.
Aggregate PnL delta: `1961.44`.
New-scope changed signals: `2`.

## Production Impact
```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
```
