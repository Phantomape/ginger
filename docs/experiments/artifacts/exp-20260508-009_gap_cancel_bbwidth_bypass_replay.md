# exp-20260508-009 Gap Cancel BB-Width Bypass Replay

## Decision

- decision: rejected
- gate4 passed: False
- production orders changed: false
- shared policy changed: false

## Metrics

| Window | EV Before | EV After | EV Delta | Sharpe Daily Delta | PnL Delta | Trades Delta | Bypasses |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.6257 | 3.8321 | +0.2064 | +0.1000 | +2746.59 | +2 | 2 |
| mid_weak | 1.5478 | 1.3149 | -0.2329 | -0.1700 | -5366.79 | +0 | 2 |
| old_thin | 0.3359 | 0.3248 | -0.0111 | -0.0500 | +165.42 | +3 | 3 |

## Bypass Events

- late_strong 2026-01-14 SLV: adverse_gap_down_cancel, gap=-0.045175, bbwidth20=0.395271
- late_strong 2026-04-14 CRDO: gap_cancel, gap=0.031469, bbwidth20=0.576781
- mid_weak 2025-06-03 CRDO: gap_cancel, gap=0.015434, bbwidth20=0.386307
- mid_weak 2025-06-24 COIN: gap_cancel, gap=0.045763, bbwidth20=0.405055
- old_thin 2024-11-21 SNOW: gap_cancel, gap=0.021301, bbwidth20=0.386325
- old_thin 2024-12-03 CRDO: gap_cancel, gap=0.020088, bbwidth20=0.525594
- old_thin 2024-12-13 AVGO: gap_cancel, gap=0.031077, bbwidth20=0.322559

## Production Parity

This replay did not alter shared production/backtest policy. If a future retry passes the three-window gate, the bypass must be implemented in `quant/production_parity.py` and surfaced in the daily execution note before it can affect live orders.
