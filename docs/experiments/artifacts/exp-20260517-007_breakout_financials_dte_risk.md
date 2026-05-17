# exp-20260517-007 Breakout Financials DTE Risk

Decision: `rejected_breakout_financials_dte_risk`.

Single variable: `BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER` for already-qualified `breakout_long` Financials signals with the existing 8-14 DTE state. Entries, candidate pool, ranking, exits, targets, LLM/news, portfolio heat, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Sample | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|:---:|---:|
| 0.000 | no | FAIL | -0.5609 | $-10,574.84 | mid_weak | late_strong | 2 | FAIL | +0.0000 |
| 0.125 | no | FAIL | +0.0274 | $+566.73 | late_strong, mid_weak | - | 2 | FAIL | +0.0000 |
| 0.250 | yes | FAIL | +0.0000 | $+0.00 | - | - | 2 | FAIL | +0.0000 |
| 0.500 | no | FAIL | -0.0423 | $-998.30 | - | late_strong, mid_weak | 2 | FAIL | +0.0002 |

Selected non-control multiplier: `0.125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1467 | +0.0106 | $116,727.26 | $116,971.75 | $+244.49 | -0.0001 | 0.8039 |
| mid_weak | 2.1313 | 2.1481 | +0.0168 | $77,222.87 | $77,545.11 | $+322.24 | +0.0000 | 0.7925 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | +0.0000 | 0.8667 |

Production impact: replay-only scout. A positive promotion would be a shared constants-only sizing change used by both `backtester.py` and `run.py`, followed by focused attribution/parity tests.
