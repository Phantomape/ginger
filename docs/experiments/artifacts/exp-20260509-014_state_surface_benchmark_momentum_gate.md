# exp-20260509-014 State-Surface Benchmark Momentum Gate

Decision: `promising_replay_only_benchmark_momentum_gate`

Alpha search, replay-only. Tests whether the state-surface satellite should participate only after a 20-day core warm-up and positive SPY/QQQ 20-day momentum.

## Three-Window Result

| Window | Event-State EV | Full Stack EV | Momentum-Gated EV | vs Event EV | vs Full EV | vs Full PnL | vs Full Sharpe | vs Full DD | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8980 | 4.8701 | 5.8806 | +0.9826 | +1.0105 | $+8,306.10 | +0.55 | -0.80% | 12 |
| mid_weak | 2.3533 | 3.2138 | 3.0350 | +0.6817 | -0.1788 | $-221.89 | -0.20 | +0.88% | 18 |
| old_thin | 0.4231 | 0.9292 | 0.7936 | +0.3705 | -0.1356 | $-3,564.29 | -0.15 | -1.52% | 12 |

## Aggregate

- Versus event-state add-on: EV +2.0348 (+26.51%), PnL $+39,729.22 (+19.47%), EV windows 3/0.
- Versus full exp-20260509-012 stack: EV +0.6961 (+7.72%), PnL $+4,519.92 (+1.89%), EV windows 1/2.

## Decision Rationale

Promising replay-only lead: the benchmark-momentum gate improves all three windows versus the event-state add-on, improves aggregate EV and PnL versus the ungated exp-20260509-012 full stack, and fixes the late_strong stack risk flag. It is not a production/default promotion because mid_weak and old_thin still give back EV versus the ungated full stack.

## Production Impact

Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, exits, or adapters changed. A promoted version needs shared run.py/backtester.py policy plus parity tests.
