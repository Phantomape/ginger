# exp-20260505-032 Enterprise Infrastructure Incumbent Basket

Decision: `rejected`

## Hypothesis

A tiny enterprise infrastructure incumbent basket may extend the existing A/B trend and breakout engine without adding noisy short-history, leveraged, macro ETF, or speculative event tickers. AKAM and ORCL are liquid mature infrastructure names tied to cloud, edge delivery, and database/platform spend, so their signals should compete more like existing core large caps than like broad watchlist noise.

## Sub-basket

`AKAM`, `ORCL`

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.1894 | -3178.23 | +0.44 | +0.0120 | -0.0833 | +4 | 3 | -1199.57 |
| `mid_weak` | +0.1348 | +1687.53 | +0.16 | -0.0420 | +0.0217 | +1 | 2 | +5799.19 |
| `old_thin` | -0.0325 | -658.55 | -0.10 | +0.0039 | +0.0076 | +2 | 1 | -3203.91 |

## Aggregate

- EV delta sum: `+0.2917` (+5.73%)
- PnL delta sum: `$-2,149.25` (-1.37%)
- EV windows improved/regressed: `2` / `1`
- Sub-basket trade count / PnL: `6` / `$+1,395.71`

## Parity

No production universe or order path changed. A promotion would need universe governance or a default-off pilot adapter before live orders.
