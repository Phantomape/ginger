# exp-20260515-008 Clean-SPY Cap-Only Leader Cap

Decision: `accepted_for_shared_policy_implementation`.

Single variable: max-position cap for already-qualified clean-SPY leaders that received the accepted clean-SPY cap but not the clean-SPY 1.10x post-sizing top-up. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.550 | PASS | +0.0498 | $+1,245.97 | late_strong, mid_weak, old_thin | - | 10 | +0.0007 |
| 0.575 | PASS | +0.0986 | $+2,466.45 | late_strong, mid_weak, old_thin | - | 10 | +0.0015 |
| 0.600 | PASS | +0.1809 | $+4,488.22 | late_strong, mid_weak, old_thin | - | 12 | +0.0022 |

## Selected Candidate

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5715 | 4.7144 | +0.1429 | $104,612.99 | $107,875.49 | $+3,262.50 | +0.0022 | 0.8039 | 5 |
| mid_weak | 1.9019 | 1.9376 | +0.0357 | $70,437.12 | $71,496.04 | $+1,058.92 | +0.0000 | 0.7925 | 3 |
| old_thin | 0.4920 | 0.4943 | +0.0023 | $34,645.58 | $34,812.38 | $+166.80 | +0.0012 | 0.9167 | 4 |

Production impact: shadow scout only. Positive promotion requires a shared `portfolio_engine` policy plus attribution/parity tests before live/default behavior changes.
