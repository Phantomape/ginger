# exp-20260516-007 gap_cancel_pullback_entry_replacement

- decision: `rejected_gap_cancel_pullback_entry`
- hypothesis: Some high-quality core candidates currently have zero contribution only because the next open breaches the upside gap-cancel threshold. Keeping only those already-qualified rank-1/TQS>=0.95 gap-canceled candidates on a three-session pullback watch may add positive replacement value without changing the raw candidate pool.
- changed_variable: `gap_cancel_pullback_entry_enabled`
- replacement_trades: `3`
- aggregate_ev_delta: `0.6019`
- aggregate_pnl_delta: `$7,876.57`

## Three-Window Metrics

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | After DD | Repl Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.7224 | +0.6160 | $116,319.10 | $124,668.47 | $+8,349.37 | 0.0665 | 1 |
| mid_weak | 2.0987 | 2.0987 | +0.0000 | $76,035.04 | $76,035.04 | $+0.00 | 0.1063 | 0 |
| old_thin | 0.5294 | 0.5153 | -0.0141 | $37,282.59 | $36,809.79 | $-472.80 | 0.1004 | 2 |

## Production Impact

Replay-only paper scout. No shared policy, backtester adapter, or run adapter was changed.

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
```
