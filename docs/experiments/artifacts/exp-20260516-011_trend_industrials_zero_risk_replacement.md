# exp-20260516-011 Trend Industrials Zero-Risk Replacement

Decision: `rejected_trend_industrials_zero_risk_replacement`.

Single variable: replay-only nonzero value for `TREND_INDUSTRIALS_RISK_MULTIPLIER` on existing `trend_long` / Industrials signals. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and the separate `breakout_long` Industrials gap rule were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Signals | Entered | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|
| 0.10 | FAIL | -0.8913 | $-35,789.86 | late_strong | mid_weak, old_thin | 9 | 9 | +0.0184 |
| 0.25 | FAIL | -0.9040 | $-36,776.06 | late_strong | mid_weak, old_thin | 9 | 9 | +0.0213 |
| 0.50 | FAIL | -0.9366 | $-38,472.58 | late_strong | mid_weak, old_thin | 9 | 9 | +0.0252 |

Selected multiplier: `0.1`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Survival | Signals | Entered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1423 | +0.0079 | $116,686.40 | $116,866.82 | $+180.42 | +0.0000 | 0.8039 | 3 | 3 |
| mid_weak | 2.1016 | 1.6228 | -0.4788 | $76,421.93 | $63,392.39 | $-13,029.54 | -0.0514 | 0.8125 | 3 | 3 |
| old_thin | 0.5294 | 0.1090 | -0.4204 | $37,282.59 | $14,341.85 | $-22,940.74 | +0.0184 | 0.8710 | 3 | 3 |

Production impact: replay-only scout. Positive promotion requires changing the shared constant or policy, adding focused parity tests, and rerunning the canonical three-window backtest before live behavior changes.
