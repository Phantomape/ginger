# exp-20260518-019 Core Misfit Conditioned Short Shadow

Decision: `promising_replay_only_conditioned_short_shadow_not_live_promotable`.

Fixed short policy is locked to `fixed_10d`; this experiment only sweeps production-visible condition gates.

| Gate | Trades | PnL | Win rate | Positive windows | Worst trade | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| all_identity | 9 | $6,079.66 | 66.67% | 1 | -4.53% | 0.73% |
| trend_long_only | 7 | $5,799.05 | 71.43% | 2 | -2.03% | 0.20% |
| breakout_long_only | 2 | $280.61 | 50.00% | 1 | -4.53% | 0.78% |
| not_risk_on_tagged | 6 | $5,582.15 | 66.67% | 2 | -2.03% | 0.20% |
| risk_on_tagged | 3 | $497.51 | 66.67% | 1 | -4.53% | 0.78% |
| available_slots_lte_3 | 5 | $5,702.10 | 80.00% | 2 | -0.37% | 0.19% |
| trade_quality_gte_0_95 | 4 | $313.86 | 75.00% | 1 | -2.03% | 0.01% |
| trade_quality_lt_0_95 | 5 | $5,765.80 | 60.00% | 1 | -4.53% | 0.74% |
| target_mult_gte_6 | 4 | $105.77 | 75.00% | 2 | -2.03% | 0.01% |

Selected gate: `trend_long_only`.
Condition gate passed: `True`.
Live short promotable: `False`.
