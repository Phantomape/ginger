# exp-20260515-003 Confirmed RS20 Mid-Dispersion Cap

Decision: `rejected_confirmed_rs20_mid_dispersion_cap`.

Single variable: max-position cap available only to `rs20_entry_state_leader=true` trend/breakout signals where `signal_day_ticker_outperformed_spy=true` and `mid_sector_dispersion=true`. RS20 scalar, mid-dispersion scalar, entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.550 | FAIL | -0.2053 | $+7,445.43 | mid_weak, old_thin | late_strong | 16 | +0.0223 |
| 0.575 | FAIL | -0.1945 | $+9,625.05 | mid_weak, old_thin | late_strong | 19 | +0.0259 |
| 0.600 | FAIL | -0.1862 | $+12,159.72 | mid_weak, old_thin | late_strong | 20 | +0.0294 |

Selected cap: `0.6`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5715 | 4.2866 | -0.2849 | $104,612.99 | $111,335.35 | $+6,722.36 | +0.0294 | 0.8039 | 3 |
| mid_weak | 1.9019 | 1.9310 | +0.0291 | $70,437.12 | $71,520.63 | $+1,083.51 | +0.0001 | 0.7925 | 6 |
| old_thin | 0.4920 | 0.5616 | +0.0696 | $34,645.58 | $38,999.43 | $+4,353.85 | +0.0027 | 0.9167 | 11 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
