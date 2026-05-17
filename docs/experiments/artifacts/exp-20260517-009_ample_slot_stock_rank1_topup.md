# exp-20260517-009 Ample-Slot Stock Rank-1 Top-Up

Decision: `accepted`.

Single variable: cap-aware post-selection top-up on the already-selected rank-1 signal when the shared entry planner has at least four available slots, excluding ETF and Commodity sectors. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0079 | $+232.83 | late_strong, mid_weak | - | 5 | late_strong, mid_weak | +0.0004 |
| 1.0250 | no | FAIL | +0.0130 | $+647.08 | late_strong, mid_weak | - | 5 | late_strong, mid_weak | +0.0016 |
| 1.0500 | no | PASS | +0.0356 | $+1,232.90 | late_strong, mid_weak | - | 6 | late_strong, mid_weak | +0.0036 |

Selected non-control multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1628 | +0.0267 | $116,727.26 | $117,072.92 | $+345.66 | +0.0000 | 0.8039 | 4 |
| mid_weak | 2.1313 | 2.1402 | +0.0089 | $77,222.87 | $78,110.11 | $+887.24 | +0.0036 | 0.7925 | 2 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | +0.0000 | 0.8667 | 0 |

## Promotion Validation

Production impact: promoted to shared `production_parity.py` with constants in
`quant/constants.py`, sizing attribution in `quant/backtester.py`, and focused
parity tests in `quant/test_production_parity.py`. `backtester.py` and
`run.py` both use the same `plan_entry_candidates` path, so this is not a
backtest-only rule.

Validation:

- `python -m pytest quant/test_production_parity.py` -> 41 passed.
- Canonical `late_strong` rerun -> EV `5.1628`, PnL `$117,072.92`, Sharpe daily `4.41`, max DD `6.65%`, trades `18`, survival `80.39%`.
- Canonical `mid_weak` rerun -> EV `2.1402`, PnL `$78,110.11`, Sharpe daily `2.74`, max DD `11.19%`, trades `21`, survival `79.25%`.
- Canonical `old_thin` rerun -> EV `0.5911`, PnL `$39,667.96`, Sharpe daily `1.49`, max DD `10.01%`, trades `22`, survival `86.67%`.
