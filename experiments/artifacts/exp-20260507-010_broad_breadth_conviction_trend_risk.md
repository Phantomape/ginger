# exp-20260507-010: Broad-Breadth Conviction Trend Risk

Decision: `rejected`
Best variant: `conviction_breadth_trend_1_50x`

## Variant Summary

| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | Resized Signals | Touched Trades | DD Max Delta | Min Sharpe Delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| conviction_breadth_trend_1_50x | False | 0.0348 | 858.13 | 1/0 | 5 | 4 | 0.0 | 0.0 |
| conviction_breadth_trend_2_00x | False | 0.0348 | 858.13 | 1/0 | 5 | 4 | 0.0 | 0.0 |

## Interpretation

Best variant `conviction_breadth_trend_1_50x` did not pass Gate 4. The existing accepted stack should remain unchanged; do not retry nearby broad-breadth conviction multipliers without new forward evidence or a materially different discriminator.

## Production Impact

- No production code was changed by this replay.
- If accepted later, the breadth field and conviction rule must live in shared policy consumed by run.py and backtester.py.
