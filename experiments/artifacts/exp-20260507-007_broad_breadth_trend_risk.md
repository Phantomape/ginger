# exp-20260507-007: Broad-Breadth Trend Risk

Decision: rejected
Best variant: broad_breadth_trend_2_00x

## Aggregate

- EV sum before: 5.6272
- EV sum after: 5.7704
- EV delta: 0.1432 (0.025448)
- PnL delta: 12781.81 (0.076379)
- Windows EV improved/regressed: 2/0
- Signals resized: 49

## Gate 4 Read

Gate 4 failed: best variant raised aggregate PnL but did not clear the north-star EV threshold and worsened risk quality, so it does not justify another breadth-conditioned sizing rule.

## Production Parity

No production code was retained. A promotion would need the breadth field in shared risk enrichment and the multiplier in shared sizing.
