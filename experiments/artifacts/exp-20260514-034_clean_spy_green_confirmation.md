# exp-20260514-034 Clean SPY Green Confirmation

Decision: `rejected_clean_spy_green_confirmation`.

Single variable: require `signal_day_ticker_green_candle=True` before the accepted clean SPY-relative signal-day top-up/cap can apply. No entries, ranking, exits, universe, LLM/news, heat, slots, or other sizing rules changed.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4853 | +0.0000 | $103,112.67 | $103,112.67 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.8580 | 1.8580 | +0.0000 | $69,070.09 | $69,070.09 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4749 | 0.4749 | +0.0000 | $33,921.46 | $33,921.46 | $+0.00 | +0.0000 | 0.9167 | 0 |

## Gate 4

- Passed: `False`
- Aggregate dEV: `+0.0000`
- Aggregate dPnL: `$+0.00`
- Improved windows: `[]`
- Regressed windows: `[]`
- Adjusted signal count: `0`
- Adjusted trade count: `0`

Production impact: shadow scout only unless promoted into shared `portfolio_engine.py`; the shared policy is called by both `backtester.py` and `run.py`.
