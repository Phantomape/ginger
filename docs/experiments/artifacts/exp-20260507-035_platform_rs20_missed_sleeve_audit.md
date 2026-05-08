# exp-20260507-035 Platform RS20 Missed Sleeve Audit

## Decision

- decision: observed_only_underpowered
- missed candidate count: 6
- fixed-notional PnL: 7971.93
- win rate: 0.5
- single ticker positive share: 0.8776

## By Window

- late_strong: count=2, pnl=-1997.32, win_rate=0.0
- mid_weak: count=1, pnl=843.79, win_rate=1.0
- old_thin: count=3, pnl=9125.46, win_rate=0.6667

## Notes

- Observed-only fixed-notional sleeve audit.
- Does not change production signals, sizing, orders, or core slots.
- Intended to decide whether missed platform RS20 candidates deserve a future sleeve replay.
