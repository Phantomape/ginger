# exp-20260510-029 SEC Financial-Report RS20 Slice

Decision: `observed_only_stronger_oracle_feature_candidate`

## Primary Slice

- source 10d avg: `0.022332`
- RS20 10d avg: `0.034878`
- RS20 valid 10d rows: `83`
- RS20 10d win rate: `0.5904`
- RS20 positive 10d windows: `3/3`
- max single ticker positive PnL share: `0.341`
- gate passed: `True`

## Diagnostic Only

- non-platform RS20 10d avg: `0.045087`
- non-platform RS20 valid 10d rows: `67`
- non-platform RS20 win rate: `0.5821`

## Notes

- Observed-only. No production orders, sizing, ranking, exits, or slots changed.
- Non-platform is reported only as a diagnostic because it would add a second causal variable.
