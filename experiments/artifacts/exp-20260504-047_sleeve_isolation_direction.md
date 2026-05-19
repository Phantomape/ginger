# exp-20260504-047 Sleeve Isolation Direction

Alpha hypothesis: isolate the executable A/B sleeves to determine whether the next alpha work should prioritize trend lifecycle management or breakout candidate quality.

No production behavior changed. The experiment used the canonical snapshots from docs/backtesting.md.

## Baseline

| Window | EV | PnL | Sharpe daily | Max DD | Win rate | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78600.33 | 4.35 | 0.0541 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.4415 | 55015.08 | 2.62 | 0.0879 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3179 | 24642.07 | 1.29 | 0.0805 | 0.4091 | 22 | 0.9167 |

## Variant Deltas

### trend_only

| Window | EV delta | PnL delta | Sharpe delta | DD improvement | Trade delta |
|---|---:|---:|---:|---:|---:|
| late_strong | -2.2434 | -48906.82 | -0.39 | 0.0161 | -8 |
| mid_weak | -0.5507 | -22503.20 | 0.12 | 0.0339 | 0 |
| old_thin | -0.0159 | -1761.70 | 0.03 | 0.0020 | -2 |

### breakout_only

| Window | EV delta | PnL delta | Sharpe delta | DD improvement | Trade delta |
|---|---:|---:|---:|---:|---:|
| late_strong | -2.5393 | -46844.10 | -1.58 | -0.0005 | 0 |
| mid_weak | -1.4122 | -50362.41 | -1.99 | -0.0272 | -3 |
| old_thin | -0.3152 | -26895.90 | -1.41 | -0.0458 | 1 |

## Decision

Rejected for production. Neither broad sleeve isolation improved the canonical three-window expected-value profile without EV regression. The useful alpha direction is not disabling a sleeve; it is improving trend lifecycle and breakout candidate quality inside the current A+B portfolio.

Production impact: experiment-only. A positive future sleeve-routing rule must be implemented through shared production/backtest policy before live use.
