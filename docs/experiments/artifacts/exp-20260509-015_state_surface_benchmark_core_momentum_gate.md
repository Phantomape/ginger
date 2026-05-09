# exp-20260509-015 State-Surface Benchmark + Core Momentum Gate

Decision: `rejected`

Alpha search, replay-only. Tests whether the state-surface satellite should participate only when both SPY/QQQ 20-day momentum and accepted-core 20-day equity momentum are positive.

## Three-Window Result

| Window | Event-State EV | Full Stack EV | Gated EV | vs Event EV | vs Full EV | vs Full PnL | vs Full Sharpe | vs Full DD | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8980 | 4.8701 | 5.8806 | +0.9826 | +1.0105 | $+8,306.10 | +0.55 | -0.80% | 12 |
| mid_weak | 2.3533 | 3.2138 | 3.2449 | +0.8916 | +0.0311 | $+2,463.42 | -0.07 | +0.88% | 15 |
| old_thin | 0.4231 | 0.9292 | 0.5151 | +0.0920 | -0.4141 | $-13,543.98 | -0.44 | -0.20% | 12 |

## Aggregate

- Versus event-state add-on: EV +1.9662 (+25.62%), PnL $+32,434.84 (+15.90%), EV windows 3/0.
- Versus full exp-20260509-012 stack: EV +0.6275 (+6.96%), PnL $-2,774.46 (-1.16%), EV windows 2/1.

## Decision Rationale

Rejected: adding core-equity positive momentum confirmation did not beat the previous benchmark-only participation gate with enough three-window stability and materiality.

## Production Impact

Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, exits, or adapters changed. Any promoted version needs shared run.py/backtester.py policy plus parity tests.
