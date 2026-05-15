# exp-20260515-028 Core Confirmed Quality Risk

Decision: `accepted_for_shared_policy_implementation`.

Single variable: cap-aware post-sizing risk top-up for core `trend_long` and `breakout_long` signals with `trade_quality_score >= 0.95`, `rs20_entry_state_leader=true`, and `signal_day_ticker_green_candle=true`. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.02 | PASS | +0.0206 | $+900.22 | late_strong, old_thin | - | 14 | +0.0012 |
| 1.05 | PASS | +0.0576 | $+1,936.96 | late_strong, mid_weak, old_thin | - | 19 | +0.0032 |
| 1.06 | PASS | +0.0780 | $+2,431.60 | late_strong, mid_weak, old_thin | - | 19 | +0.0045 |
| 1.07 | PASS | +0.0852 | $+2,593.10 | late_strong, mid_weak, old_thin | - | 19 | +0.0049 |
| 1.07 | PASS | +0.0866 | $+2,604.84 | late_strong, mid_weak, old_thin | - | 19 | +0.0049 |
| 1.08 | FAIL | +0.0865 | $+2,813.87 | late_strong, mid_weak, old_thin | - | 20 | +0.0057 |
| 1.09 | FAIL | +0.1041 | $+2,942.63 | late_strong, mid_weak, old_thin | - | 20 | +0.0061 |

Selected multiplier: `1.075`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0334 | 5.1064 | +0.0730 | $115,183.05 | $116,319.10 | $+1,136.05 | 0.8039 | 5 |
| mid_weak | 2.0900 | 2.0987 | +0.0087 | $74,906.73 | $76,035.04 | $+1,128.31 | 0.7925 | 6 |
| old_thin | 0.5245 | 0.5294 | +0.0049 | $36,942.11 | $37,282.59 | $+340.48 | 0.8667 | 8 |

Production impact: replay-only scout. Positive promotion requires shared `portfolio_engine` attribution and production parity coverage before live/default behavior changes.
