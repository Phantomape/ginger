# exp-20260525-024 Volatility-Contraction Shared Paper Adapter

Decision: `accepted_shared_default_off_volatility_contraction_paper_adapter`.

This accepts the shared default-off forward paper adapter for the exp-20260525-022 QQQ-confirmed volatility-contraction lead. It does not enable live orders or alter core trading behavior.

## Source Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1652 | +0.0024 | $117,072.92 | $117,394.96 | $+322.04 |
| mid_weak | 2.1402 | 3.1574 | +1.0172 | $78,110.11 | $93,694.84 | $+15,584.73 |
| old_thin | 0.5911 | 0.8208 | +0.2297 | $39,667.96 | $47,170.75 | $+7,502.79 |

## Aggregate

- EV delta: `1.2493` (`0.158257`)
- PnL delta: `$23409.56` (`0.099678`)
- target trades: `71`
- windows EV/PnL regressed: `0` / `0`

## Production Parity

Shared helper plus `run.py`, report, and default-off attribution wiring. Trade enabled is false and activation requires a separate Gate 1-4 experiment.

No JavaScript was used.
