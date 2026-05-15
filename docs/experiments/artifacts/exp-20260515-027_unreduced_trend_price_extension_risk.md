# exp-20260515-027 Unreduced Trend Price Extension Risk

Decision: `rejected_unreduced_trend_price_extension_risk`.

Single variable: restrict the accepted 1.125x trend-only price-vs-200MA extension top-up to signals with no pre-existing risk-haircut multiplier. Entries, exits, ranking, universe, LLM/news, heat, slots, broad price-extension top-up, and the accepted scalar were unchanged.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0334 | 5.0334 | +0.0000 | $115,183.05 | $115,183.05 | $+0.00 | +0.0000 | 0.8039 | 1 |
| mid_weak | 2.0900 | 2.0894 | -0.0006 | $74,906.73 | $74,889.81 | $-16.92 | +0.0000 | 0.7925 | 2 |
| old_thin | 0.5245 | 0.5240 | -0.0005 | $36,942.11 | $36,895.35 | $-46.76 | +0.0000 | 0.9000 | 2 |

Production impact: shadow scout only unless promoted into shared `portfolio_engine.py`, backtest attribution, and focused parity tests.
