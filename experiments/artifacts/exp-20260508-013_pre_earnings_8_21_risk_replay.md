# exp-20260508-013 Pre-Earnings 8-21 Risk Replay

Decision: `rejected`
Best variant: `pre_earnings_8_21_0_75x_replay`

## Hypothesis

Accepted A/B trades 8-21 calendar days before the next earnings date may represent a distinct pre-event risk bucket. If the bucket is a noisy overhang, 0.50x/0.75x should improve weak-window EV; if it is anticipation momentum, 1.25x should improve EV without hurting old_thin drawdown.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.6272 | 167347.95 | 62 |

## Aggregate Replay

| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| pre_earnings_8_21_0_50x_replay | -0.0929 | -0.011245 | -2689.12 | -0.016069 | 1/2 | 13 | 13 | 0.0054 | 0.3221 | FAIL |
| pre_earnings_8_21_0_75x_replay | -0.0295 | -0.003571 | -1324.28 | -0.007913 | 1/2 | 13 | 13 | 0.0018 | 0.3187 | FAIL |
| pre_earnings_8_21_1_25x_cap_aware | -0.0787 | -0.009526 | -1068.77 | -0.006387 | 1/2 | 13 | 13 | 0.0039 | 0.9202 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |
|---|---|---:|---:|---:|---:|
| pre_earnings_8_21_0_50x_replay | late_strong | -0.087 | -3011.71 | 0.11 | -0.008 |
| pre_earnings_8_21_0_50x_replay | mid_weak | -0.118 | -1612.31 | -0.08 | 0.0054 |
| pre_earnings_8_21_0_50x_replay | old_thin | 0.1121 | 1934.9 | 0.23 | -0.0079 |
| pre_earnings_8_21_0_75x_replay | late_strong | -0.0287 | -1505.09 | 0.07 | -0.008 |
| pre_earnings_8_21_0_75x_replay | mid_weak | -0.056 | -787.13 | -0.03 | 0.0018 |
| pre_earnings_8_21_0_75x_replay | old_thin | 0.0552 | 967.94 | 0.11 | -0.004 |
| pre_earnings_8_21_1_25x_cap_aware | late_strong | -0.0408 | -430.88 | -0.02 | 0.0001 |
| pre_earnings_8_21_1_25x_cap_aware | mid_weak | 0.0083 | 188.61 | 0.0 | 0.0 |
| pre_earnings_8_21_1_25x_cap_aware | old_thin | -0.0462 | -826.5 | -0.1 | 0.0039 |

## Rejection Reason

Best variant `pre_earnings_8_21_0_75x_replay` failed Gate 4: EV delta -0.0295 (-0.003571), PnL delta -1324.28 (-0.007913), windows improved/regressed 1/2, changed trades 13 of 13 touched, max DD worsening 0.0018, single ticker positive share 0.3187.

## Production Impact

Replay-only diagnostic. No shared policy, default backtest strategy, production orders, LLM/news boundary, or universe changed.
