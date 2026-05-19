# exp-20260515-007 Mid-Score Plain Risk-On Cap

Decision: `rejected_mid_score_plain_risk_on_cap`.

Single variable: max-position cap for otherwise-unmodified risk-on signals that already use the accepted mid-score 1.6x sizing path. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.425 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.450 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.475 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.500 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |

## Selected Candidate

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5715 | 4.5715 | +0.0000 | $104,612.99 | $104,612.99 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.9019 | 1.9019 | +0.0000 | $70,437.12 | $70,437.12 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4920 | 0.4920 | +0.0000 | $34,645.58 | $34,645.58 | $+0.00 | +0.0000 | 0.9167 | 0 |

Production impact: shadow scout only. Positive promotion requires a shared `portfolio_engine` policy plus attribution/parity tests before live/default behavior changes.
