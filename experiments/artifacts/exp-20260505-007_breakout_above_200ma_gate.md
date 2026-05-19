# exp-20260505-007 Breakout Above-200MA Gate

## Result

Rejected. Rejected: the hard gate did not produce a stable, material improvement across the fixed windows.

| window | EV before | EV after | PnL delta | Sharpe delta | Win-rate delta | Trades delta | Dropped candidates |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.4191 | 0.00 | 0.00 | 0.0000 | 0.0 | 0 |
| mid_weak | 1.4415 | 1.4415 | 0.00 | 0.00 | 0.0000 | 0.0 | 0 |
| old_thin | 0.3179 | 0.3179 | 0.00 | 0.00 | 0.0000 | 0.0 | 0 |

## Decision

- Decision: rejected.
- Production impact: {"backtester_adapter_changed": false, "parity_test_added": false, "promotion_requirement": "If accepted, update shared quant/signal_engine.py only; both backtester.py and run.py already call generate_signals from that module.", "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}
- Next evidence needed: Candidate audit evidence that a moving-average gate actually touches Strategy B signals.
