# exp-20260510-024 SEC Financial-Report T+1 Drift Slice

Decision: `observed_only_forward_paper_queue_candidate`

## Aggregate

- candidates: `193`
- valid 10d candidates: `184`
- positive 10d avg windows: `3/3`
- 10d avg return: `0.022332`
- 10d win rate: `0.538`
- 20d avg return: `0.03815`
- gate passed: `True`

## Windows

### late_strong

- candidates: `61`
- 10d avg: `0.020843`
- 10d win rate: `0.4407`

### mid_weak

- candidates: `63`
- 10d avg: `0.03398`
- 10d win rate: `0.7069`

### old_thin

- candidates: `69`
- 10d avg: `0.01356`
- 10d win rate: `0.4776`

## Notes

- Observed-only slice. It does not change production orders or core backtest behavior.
- The right next step is a default-off forward paper queue, not production promotion.
