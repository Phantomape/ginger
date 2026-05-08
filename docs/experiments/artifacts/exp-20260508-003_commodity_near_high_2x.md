# exp-20260508-003 Commodity Near-High 2.0x Replay

## Hypothesis

The accepted `trend_long + Commodities + pct_from_52w_high >= -0.03` sleeve might still be under-budgeted. Test only `TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER = 2.0` versus the current `1.5`.

## Result

Rejected. The change was directionally positive but economically too small:

| Window | EV before | EV after | PnL before | PnL after | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| late_strong | 3.6257 | 3.6914 | 82,030.12 | 83,140.28 | improved, immaterial |
| mid_weak | 1.5478 | 1.5478 | 57,542.74 | 57,542.74 | unchanged |
| old_thin | 0.3359 | 0.3359 | 26,242.68 | 26,242.68 | unchanged |

Aggregate EV improved `+0.0657` (`+1.19%`) and aggregate PnL improved `$1,110.16` (`+0.67%`). This misses the Gate 4 thresholds.

## Interpretation

The Commodity near-high sleeve remains strong, but the next raw multiplier is not the bottleneck. Position caps and existing stack constraints absorb most of the extra budget. Do not continue nearby Commodity scalar-only retries without new cap-room, macro, event, or forward concentration evidence.
