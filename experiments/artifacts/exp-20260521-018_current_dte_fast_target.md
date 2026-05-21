# exp-20260521-018 Current DTE Fast Target

Decision: `rejected_current_dte_fast_target`.

Single variable: cap target width for existing accepted current-stack DTE risk cohorts. Entries, ranking, sizing, universe, LLM, news, heat, and stops stay locked.

## Sweep

| Target cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Trades | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|---:|
| control | CTRL | +0.0000 | $+0.00 | - | - | 0 | 0 | 61 | +0.0000 |
| 3.50 | FAIL | +0.0000 | $+0.00 | - | - | 16 | 3 | 61 | +0.0000 |
| 3.00 | FAIL | +0.0000 | $+0.00 | - | - | 16 | 3 | 61 | +0.0000 |
| 2.50 | FAIL | +0.0009 | $+39.01 | mid_weak, old_thin | - | 16 | 3 | 61 | +0.0000 |
| 2.00 | FAIL | -0.0856 | $-3,333.24 | mid_weak | old_thin | 16 | 3 | 62 | +0.0000 |

Selected target cap: `2.5`.

## Selected three-window result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | +0.0000 | 0.8039 | 4 |
| mid_weak | 2.1402 | 2.1410 | +0.0008 | $78,110.11 | $78,141.87 | $+31.76 | +0.0000 | 0.7925 | 6 |
| old_thin | 0.5911 | 0.5912 | +0.0001 | $39,667.96 | $39,675.21 | $+7.25 | +0.0000 | 0.8667 | 6 |

Production impact: replay-only scout unless a selected cap is promoted into shared risk policy and rerun through the canonical three-window protocol.
