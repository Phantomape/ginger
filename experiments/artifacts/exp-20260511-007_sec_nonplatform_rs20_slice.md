# exp-20260511-007 SEC Non-Platform RS20 Slice

Decision: `observed_only_rejected_concentration`

## Result

- baseline RS20 10d avg: `0.034878`
- non-platform RS20 10d avg: `0.045087`
- non-platform valid 10d rows: `67`
- non-platform 10d win rate: `0.5821`
- positive 10d windows: `3/3`
- max single ticker positive PnL share: `0.375`
- gate passed: `False`
- excluded platform RS20 10d avg: `-0.007874`

## Notes

- Observed-only. No production orders, sizing, ranking, exits, or slots changed.
- The average return is stronger, but concentration failed the pre-registered guard.
