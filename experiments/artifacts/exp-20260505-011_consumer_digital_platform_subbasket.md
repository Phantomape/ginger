# exp-20260505-011 Consumer Digital Platform Sub-basket

Decision: `rejected`

## Hypothesis

A small US consumer digital platform basket may be a better extension surface than the rejected broad historical watchlist: HOOD, RBLX, and SOFI are liquid engagement/platform names where existing A/B momentum and breakout rules may capture reflexive repricing without adding leveraged, macro, or low-quality tickers.

## Sub-basket

`HOOD`, `RBLX`, `SOFI`

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | -0.2570 | -3211.76 | -0.16 | +0.0000 | -0.0357 | +1 | 1 | -1796.95 |
| `mid_weak` | +0.4803 | +19182.11 | -0.03 | +0.0022 | +0.0671 | +1 | 2 | +15886.33 |
| `old_thin` | -0.1676 | -7945.79 | -0.39 | +0.0276 | -0.0891 | +3 | 4 | -1120.96 |

## Aggregate

- EV delta sum: `+0.0557` (+1.09%)
- PnL delta sum: `$+8,024.56` (+5.11%)
- EV windows improved/regressed: `1` / `2`
- Sub-basket trade count / PnL: `7` / `$+12,968.42`

## Parity

No production universe or order path changed. A promotion would need universe governance or a default-off pilot adapter before live orders.
