# SEC FD/Other Event Sleeve Replay

Experiment: `exp-20260504-037`
Decision: `positive_sample_not_material_no_promotion`

## Hypothesis

SEC 8-K FD/Other Event filings with a strong negative first reaction may capture temporary event uncertainty that mean-reverts over the next 10 trading days as a small satellite sleeve.

## Three-Window Result

| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.5668 | 0.1477 | 78600.33 | 81432.83 | 2194.27 | 5 | 75.00% |
| mid_weak | 1.4415 | 1.5183 | 0.0768 | 55015.08 | 56652.16 | 1413.72 | 3 | 54.17% |
| old_thin | 0.3179 | 0.3507 | 0.0328 | 24642.07 | 26168.25 | 1526.18 | 4 | 46.15% |

## Event Sleeve

- Candidate count: `16`
- Selected trades: `12`
- Event PnL: `5134.17`
- Event win rate: `66.67%`
- Top absolute event contribution: `MU` 1823.48 (18.21% of abs event PnL)

## Decision

The FD/Other Event negative-reaction overlay improved the majority read without EV regression, but the effect was below material Gate 4 thresholds; keep it as observe-only event alpha.
