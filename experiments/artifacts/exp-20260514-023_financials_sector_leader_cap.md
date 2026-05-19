# exp-20260514-023 Financials Sector-Leader Cap

Decision: `accepted_for_shared_policy_implementation`.

Single variable: max position cap for the already-accepted `trend_long + Financials + financials_sector_leader=true` sleeve. Entries, exits, ranking, universe, LLM/news logic, raw Financials multipliers, heat, and slot limits were unchanged.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4313 | 4.4313 | +0.0000 | $101,873.18 | $101,873.18 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.7334 | 1.8324 | +0.0990 | $65,410.59 | $68,124.12 | $+2,713.53 | +0.0001 | 0.7925 | 3 |
| old_thin | 0.4520 | 0.4703 | +0.0183 | $32,522.26 | $33,591.36 | $+1,069.10 | +0.0024 | 0.9167 | 3 |

## Sweep

| Cap | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |
|---:|---|---:|---:|---:|---:|
| 0.45 | PASS | +0.0802 | $+2,486.78 | +0.0012 | 6 |
| 0.50 | PASS | +0.1173 | $+3,782.63 | +0.0024 | 6 |

Production impact: promoted into shared `portfolio_engine.py`; both backtest and production call the same `size_signals` path, with a focused parity test.
