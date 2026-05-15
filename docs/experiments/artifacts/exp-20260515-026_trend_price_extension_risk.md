# exp-20260515-026 Trend Price-vs-200MA Extension Risk

Decision: `accepted_and_promoted_to_shared_policy`.

Single variable: cap-aware extra post-sizing top-up for already-qualified `trend_long` non-ETF/non-commodity stocks with `price_vs_200ma_extension_state=true`. No entry filter, ranking, exit, target, universe, LLM, news, heat, slot, or broad extension-state definition changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0750 | PASS | +0.0498 | $+1,744.91 | mid_weak, old_thin | - | 12 | +0.0028 |
| 1.1000 | PASS | +0.0739 | $+2,519.86 | mid_weak, old_thin | - | 14 | +0.0038 |
| 1.1250 | PASS | +0.0943 | $+3,086.63 | mid_weak, old_thin | - | 16 | +0.0047 |
| 1.1500 | FAIL | +0.1177 | $+3,812.15 | mid_weak, old_thin | - | 16 | +0.0057 |
| 1.2000 | FAIL | +0.1349 | $+4,529.43 | mid_weak, old_thin | - | 20 | +0.0078 |

Selected multiplier: `1.125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0334 | 5.0334 | +0.0000 | $115,183.05 | $115,183.05 | $+0.00 | +0.0000 | 0.8039 | 2 |
| mid_weak | 2.0103 | 2.0900 | +0.0797 | $73,104.97 | $74,906.73 | $+1,801.76 | +0.0000 | 0.7925 | 7 |
| old_thin | 0.5099 | 0.5245 | +0.0146 | $35,657.24 | $36,942.11 | $+1,284.87 | +0.0047 | 0.9000 | 7 |

Production impact: promoted into shared `portfolio_engine.py`, `backtester.py` attribution keys, `docs/production_backtest_parity.md`, and focused parity tests. `run.py` and `backtester.py` both use the shared sizing path; the experiment runner remains a research artifact.
