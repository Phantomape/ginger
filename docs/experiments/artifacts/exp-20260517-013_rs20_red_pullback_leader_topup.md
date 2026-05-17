# exp-20260517-013 RS20 Leader Red-Pullback Top-Up

Decision: `rejected_rs20_red_pullback_leader_topup`.

Single variable: cap-aware post-sizing top-up on already-qualified trend/breakout signals with `rs20_entry_state_leader=true` and `signal_day_ticker_green_candle!=true`, excluding ETF. Entries, filters, candidate pool, ranking, exits, targets, LLM/news, event sleeves, and portfolio heat were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0026 | $+53.52 | late_strong | - | 9 | late_strong, mid_weak | +0.0000 |
| 1.0250 | no | FAIL | -0.0038 | $+177.14 | - | late_strong | 9 | late_strong, mid_weak | +0.0000 |
| 1.0500 | no | FAIL | +0.0085 | $+457.35 | late_strong | - | 10 | late_strong, mid_weak | +0.0000 |

Selected non-control multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1713 | +0.0085 | $117,072.92 | $117,530.98 | $+458.06 | -0.0001 | 0.8039 | 5 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,109.40 | $-0.71 | +0.0000 | 0.7925 | 5 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | +0.0000 | 0.8667 | 0 |

Production impact: replay-only scout. A positive promotion must implement this in shared `risk_engine.py` / `portfolio_engine.py`, add parity tests, then rerun the canonical three-window backtest before live/default behavior changes.
