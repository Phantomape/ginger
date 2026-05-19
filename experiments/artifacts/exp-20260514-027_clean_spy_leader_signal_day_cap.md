# exp-20260514-027 Clean SPY-Leader Signal-Day Cap

Decision: `accepted_for_shared_policy_implementation`.

Single variable: max position cap for signals that already qualify for the accepted clean risk-on SPY-relative leader path and also beat SPY open-to-close on the signal day. Entries, exits, ranking, universe, LLM/news logic, accepted risk multipliers, heat, and slot limits were unchanged.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4313 | 4.4853 | +0.0540 | $101,873.18 | $103,112.67 | $+1,239.49 | +0.0011 | 0.8039 | 6 |
| mid_weak | 1.8324 | 1.8502 | +0.0178 | $68,124.12 | $68,776.24 | $+652.12 | +0.0000 | 0.7925 | 5 |
| old_thin | 0.4703 | 0.4704 | +0.0001 | $33,591.36 | $33,597.15 | $+5.79 | +0.0004 | 0.9167 | 7 |

## Sweep

| Cap | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |
|---:|---|---:|---:|---:|---:|
| 0.525 | PASS | +0.0719 | $+1,897.40 | +0.0011 | 18 |
| 0.550 | FAIL | +0.1524 | $+3,624.05 | +0.0018 | 19 |
| 0.600 | FAIL | +0.2846 | $+7,077.59 | +0.0033 | 18 |

Production impact: promoted into shared `constants.py` and `portfolio_engine.py`; `backtester.py` records the attribution key, production and backtest both call `size_signals`, and focused parity tests were added.

