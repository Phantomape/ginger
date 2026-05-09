# exp-20260509-012 Event-State Add-On Plus State-Surface Stack

Decision: `promising_replay_only_additive_stack_risk_flag`

Alpha search, replay-only. Tests whether the frozen state-surface satellite adds value on top of the frozen non-generic event state add-on.

## Three-Window Result

| Window | Event EV | Stack EV | Delta EV | Event PnL | Stack PnL | Delta PnL | Sharpe Delta | DD Delta | Surface trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8980 | 4.8701 | -0.0279 | $101,828.78 | $106,102.79 | $+4,274.01 | -0.22 | +0.88% | 15 |
| mid_weak | 2.3533 | 3.2138 | +0.8605 | $72,186.99 | $85,473.62 | $+13,286.63 | +0.50 | -1.25% | 21 |
| old_thin | 0.4231 | 0.9292 | +0.5061 | $30,005.02 | $47,653.68 | $+17,648.66 | +0.54 | +5.50% | 21 |

## Aggregate Gate

- EV sum: 7.6744 -> 9.0131 (+1.3387, +17.44%)
- PnL sum: $204,020.79 -> $239,230.09 (+35,209.30, +17.26%)
- EV windows improved/regressed: 2/1
- PnL windows improved/regressed: 3/0
- Single-ticker positive share: 0.2325
- Late risk flag: `True`

## Decision Rationale

Promising only as a replay/forward-paper stack: adding the frozen state-surface sleeve to the frozen non-generic event state add-on improved aggregate EV and PnL, with EV improvement in the majority of canonical windows. It is not a live/default promotion because late_strong EV and Sharpe regressed while drawdown rose.

## Production Impact

Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, or exits changed. A positive production version would require a shared run.py/backtester.py adapter and parity tests.
