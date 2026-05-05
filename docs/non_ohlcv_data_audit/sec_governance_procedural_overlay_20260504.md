# SEC Governance/Procedural Event Overlay

Experiment: `exp-20260504-039`
Decision: `accepted_requires_trade_enabled_sleeve_parity`

## Hypothesis

Residual SEC 8-K governance/procedural filings with mild market reactions may capture temporary uncertainty absorption that can add portfolio value as a small satellite sleeve.

## Three-Window Result

| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Event Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.5745 | 0.1554 | 78600.33 | 80689.39 | 1450.84 | 4 | 69.57% |
| mid_weak | 1.4415 | 1.685 | 0.2435 | 55015.08 | 59751.94 | 4513.51 | 5 | 57.69% |
| old_thin | 0.3179 | 0.3485 | 0.0306 | 24642.07 | 26010.74 | 1368.67 | 4 | 46.15% |

## Event Sleeve

- Candidate count: `24`
- Selected trades: `13`
- Event PnL: `7333.02`
- Event win rate: `61.54%`
- Top absolute event contribution: `TRIP` 3143.71 (24.14% of abs event PnL)

## Cell Summary

| Cell | Trades | PnL | Win rate | Avg net return |
|---|---:|---:|---:|---:|
| charter_or_securities_change|positive_excess_0_to_2pct | 5 | 1398.13 | 60.00% | 2.80% |
| exhibit_only|negative_excess_0_to_minus_2pct | 1 | -92.06 | 0.00% | -0.92% |
| exhibit_only|positive_excess_0_to_2pct | 2 | 618.35 | 100.00% | 3.09% |
| shareholder_vote|negative_excess_0_to_minus_2pct | 5 | 5408.6 | 60.00% | 10.82% |

## Decision

The SEC governance/procedural event overlay cleared the fixed-window materiality gate, but cannot be enabled until a shared production/backtest event-sleeve adapter exists.
