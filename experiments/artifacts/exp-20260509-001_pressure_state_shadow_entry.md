# exp-20260509-001 Pressure State-Shadow Entry

- Decision: `rejected`
- Rejection reason: Pressure-date state-shadow entries did not clear the three-window EV-first Gate 4 bar.
- Production impact: replay only; no production strategy behavior changed.

## Three-window metrics

| Window | EV before | EV after | EV delta | PnL delta | Trades delta | Shadow injected | Shadow entered |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 3.4715 | -0.5959 | -14663.34 | 2 | 10 | 2 |
| mid_weak | 1.6195 | 1.9046 | 0.2851 | 5907.72 | 4 | 11 | 4 |
| old_thin | 0.3583 | 0.1138 | -0.2445 | -14264.80 | 4 | 12 | 5 |

## Mechanism Read

The state-aware surface is not enough as an executable pressure-date entry source. It injected candidates from existing core tickers, but any apparent added coverage must beat the live slot/heat path, not just show positive forward returns in a shadow audit.

## Do Not Repeat

Do not retry this pressure-date state-shadow entry source or nearby hard thresholds on the same snapshots unless candidate-level replacement evidence changes or the surface is tied to a new orthogonal event/news feature.
