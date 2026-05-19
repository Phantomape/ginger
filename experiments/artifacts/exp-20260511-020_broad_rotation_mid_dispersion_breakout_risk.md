# exp-20260511-020: Broad-Rotation Mid-Dispersion Breakout Risk

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
| broad_rotation_mid_dispersion_breakout_0_50x | False | -0.1966 | -6506.05 | 0/1 | 0/1 | 6 | 3 |
| broad_rotation_mid_dispersion_breakout_1_25x | False | 0.0 | 0.0 | 0/0 | 0/0 | 6 | 3 |
| broad_rotation_mid_dispersion_breakout_1_50x | False | 0.0 | 0.0 | 0/0 | 0/0 | 6 | 3 |
| broad_rotation_mid_dispersion_breakout_2_00x | False | 0.0 | 0.0 | 0/0 | 0/0 | 6 | 3 |

## Gate Answers

- Hypothesis: Breakout_long signals may deserve a larger or smaller risk budget only when small-cap participation is beating SPY and sector-level 20-day dispersion is in the accepted mid range.
- Changed variable: breakout risk multiplier only when both broad-rotation and existing mid-sector-dispersion state are true.
- Prior near experiment: exp-20260511-017 tested IWM-SPY breakout risk alone and failed; this adds the richer breadth discriminator that artifact required for any valid retry.
- Gate 2 fields: entry_date / target_price present in open positions; IWM and SPY OHLCV are available in the canonical snapshots.
- Production note: no shared policy was promoted; a future positive retry must place the combined state in shared production/backtest sizing.
