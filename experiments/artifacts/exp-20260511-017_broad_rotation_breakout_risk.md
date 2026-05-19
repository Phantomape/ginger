# exp-20260511-017: Broad-Rotation Breakout Risk

Decision: `rejected`

## Baseline

| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.234 | 94086.91 | 4.5 | 0.0548 | 0.7895 | 19 | 0.8039 |
| mid_weak | 1.6689 | 61813.4 | 2.7 | 0.0941 | 0.5238 | 21 | 0.7925 |
| old_thin | 0.3853 | 28544.11 | 1.35 | 0.0815 | 0.4091 | 22 | 0.9167 |

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| broad_rotation_breakout_0_50x | False | -1.1304 | -22446.9 | 1/2 | 1/2 | 16 | 10 |
| broad_rotation_breakout_1_25x | False | 0.1125 | 1632.65 | 1/1 | 1/1 | 16 | 10 |
| broad_rotation_breakout_1_50x | False | 0.1269 | 1740.56 | 1/1 | 1/1 | 16 | 10 |
| broad_rotation_breakout_2_00x | False | 0.1265 | 1709.03 | 1/1 | 1/1 | 16 | 10 |

## Gate Answers

- Hypothesis: Existing breakout_long candidates may deserve a state-aware risk budget when IWM 20-day momentum leads SPY by more than 2pp, because broad participation can confirm breakout follow-through.
- Changed variable: broad-rotation breakout risk multiplier only.
- Prior near experiment: broad-rotation trend risk was rejected; this tests breakout_long, not trend_long.
- Fields checked: entry_date and target_price exist in open_positions; IWM/SPY OHLCV exists in canonical snapshots.
- Production note: no production policy promoted by this replay-only runner.
