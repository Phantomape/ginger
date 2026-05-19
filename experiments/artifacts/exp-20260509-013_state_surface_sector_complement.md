# exp-20260509-013 State-Surface Sector Complement

Decision: `rejected_full_stack_replacement`

Alpha search, replay-only. Tests whether the state-surface satellite should avoid sectors already represented by active core A/B trades.

## Three-Window Result

| Window | Event-State EV | Full Stack EV | Sector-Complement EV | vs Event EV | vs Full EV | vs Full PnL | vs Full Sharpe | vs Full DD | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8980 | 4.8701 | 4.9559 | +0.0579 | +0.0858 | $+474.63 | +0.06 | -0.95% | 15 |
| mid_weak | 2.3533 | 3.2138 | 3.0341 | +0.6808 | -0.1797 | $-2,801.09 | -0.09 | +0.00% | 15 |
| old_thin | 0.4231 | 0.9292 | 0.5425 | +0.1194 | -0.3867 | $-13,097.44 | -0.38 | -0.86% | 18 |

## Aggregate

- Versus event-state add-on: EV +0.8581 (+11.18%), PnL $+19,785.40 (+9.70%), EV windows 3/0.
- Versus full exp-20260509-012 stack: EV -0.4806 (-5.33%), PnL $-15,423.90 (-6.45%), EV windows 1/2.

## Decision Rationale

Rejected as a replacement for exp-20260509-012. The same-sector complement gate fixes the late_strong EV regression and remains positive versus event-state-only, but it gives back too much aggregate EV and PnL versus the full stack, mainly by skipping high-value old_thin Technology candidates.

## Production Impact

Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, exits, or adapters changed. A positive version would require a shared run.py/backtester.py adapter and parity tests.
