# exp-20260506-004 Quality Compounder Basket

Decision: `rejected`

## Hypothesis

A small quality/defensive-growth basket may improve the universe without repeating broad ticker growth: COST, IDXX, and LRN have full fresh-snapshot OHLCV coverage, liquid single-name behavior, and cleaner business quality than recent rejected high-beta consumer, cyber, or enterprise-infra baskets.

## Sub-basket

`COST`, `IDXX`, `LRN`

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | -0.4366 | -5280.10 | -0.29 | +0.0000 | -0.0682 | +2 | 2 | -3460.33 |
| `mid_weak` | -0.7081 | -15588.20 | -0.76 | +0.0211 | -0.1392 | +5 | 3 | -5268.27 |
| `old_thin` | -0.1078 | -3628.25 | -0.29 | +0.0483 | -0.0613 | +1 | 3 | +658.40 |

## Aggregate

- EV delta sum: `-1.2525` (-24.59%)
- PnL delta sum: `$-24496.55` (-15.60%)
- EV windows improved/regressed: `0` / `3`
- PnL windows improved/regressed: `0` / `3`
- Sub-basket trade count / PnL: `8` / `$-8070.20`

## Mechanism Read

The basket did not add stabilizing quality alpha. COST/IDXX/LRN generated mostly stop-loss entries and consumed scarce slots; EV, PnL, and win rate regressed in all three windows.

## Parity

No production universe or order path changed. Any positive future retry must be promoted through universe governance or a default-off pilot adapter with run/backtester parity.
