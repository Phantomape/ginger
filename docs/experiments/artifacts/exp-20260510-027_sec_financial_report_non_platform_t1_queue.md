# exp-20260510-027 SEC Financial-Report Non-Platform T+1 Queue

Decision: `accepted_default_off_forward_queue_refinement`

## Aggregate

- source candidates: `193`
- non-platform candidates: `164`
- excluded platform_pool candidates: `29`
- non-platform valid 10d: `157`
- non-platform positive 10d avg windows: `3/3`
- source 10d avg return: `0.022332`
- non-platform 10d avg return: `0.027636`
- non-platform 10d win rate: `0.5414`
- excluded platform_pool 10d avg return: `-0.008507`
- gate passed: `True`

## Windows

### late_strong

- source candidates: `61`
- non-platform candidates: `55`
- excluded platform_pool candidates: `6`
- source 10d avg: `0.020843`
- non-platform 10d avg: `0.02468`
- platform_pool 10d avg: `-0.013055`

### mid_weak

- source candidates: `63`
- non-platform candidates: `53`
- excluded platform_pool candidates: `10`
- source 10d avg: `0.03398`
- non-platform 10d avg: `0.037729`
- platform_pool 10d avg: `0.015985`

### old_thin

- source candidates: `69`
- non-platform candidates: `56`
- excluded platform_pool candidates: `13`
- source 10d avg: `0.01356`
- non-platform 10d avg: `0.021781`
- platform_pool 10d avg: `-0.028293`

## Notes

- Observed-only candidate-pool refinement. It does not enable orders.
- The shared production/backtest policy update is allowed only for the default-off forward queue.
- Closed forward paper outcomes are still required before any live promotion.

## Verification

- Focused tests: `23 passed`.
- Three fixed-window core backtests remained unchanged:
  `late_strong` EV `4.2340`, `mid_weak` EV `1.6689`, `old_thin` EV `0.3853`.
