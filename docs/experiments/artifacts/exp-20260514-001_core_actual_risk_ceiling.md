# exp-20260514-001 Core Actual-Risk Ceiling

Decision: `rejected_core_actual_risk_ceiling`.

Single variable: post-sizing actual `risk_pct` ceiling for core `trend_long`/`breakout_long` signals. The ceiling shrinks shares after existing shared sizing helpers run; it does not change entries, ranking, exits, targets, universe, LLM, or news behavior.

## Sweep

| Risk ceiling | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.0180 | FAIL | -0.9562 | $-33,003.72 | - | late_strong, mid_weak, old_thin | 45 | -0.0071 |
| 0.0200 | FAIL | -0.6250 | $-24,159.27 | - | late_strong, mid_weak, old_thin | 37 | -0.0034 |
| 0.0225 | FAIL | -0.3586 | $-16,435.52 | - | late_strong, mid_weak, old_thin | 29 | -0.0019 |
| 0.0250 | FAIL | -0.1832 | $-10,356.44 | late_strong | mid_weak, old_thin | 20 | -0.0003 |

Selected risk ceiling: `0.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.4065 | +0.0297 | $99,695.99 | $98,136.05 | $-1,559.94 | 0.8039 | 6 |
| mid_weak | 1.6788 | 1.5296 | -0.1492 | $62,644.67 | $57,724.27 | $-4,920.40 | 0.7925 | 9 |
| old_thin | 0.4292 | 0.3655 | -0.0637 | $31,563.29 | $27,687.19 | $-3,876.10 | 0.9167 | 5 |

Production impact: replay-only scout unless Gate 4 passes and the same cap is promoted into shared `portfolio_engine` sizing with attribution parity.
