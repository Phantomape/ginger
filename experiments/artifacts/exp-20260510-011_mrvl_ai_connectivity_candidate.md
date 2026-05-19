# exp-20260510-011 MRVL AI Connectivity Candidate

Decision: `rejected`

## Hypothesis

Adding only MRVL to the candidate universe may capture AI connectivity/custom silicon momentum with less noise than the rejected broad historical watchlist expansion.

## Protocol

Three fixed windows from docs/backtesting.md. Canonical snapshots do not contain MRVL, so this replay uses the existing exp-20260505-009 fresh OHLCV snapshots over the same dates.

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | Survival delta | Trades delta | MRVL trades | MRVL PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0971 | -388.05 | -0.09 | 0.0 | 0.0074 | 2 | 2 | 1294.7 |
| mid_weak | -0.0006 | -25.32 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 |
| old_thin | -0.0379 | -1086.4 | -0.09 | 0.003 | 0.0013 | 3 | 3 | -504.82 |

## Aggregate

- EV before sum: `5.9588`
- EV delta sum: `-0.1356` (-0.022756)
- PnL before sum: `$176351.64`
- PnL delta sum: `$-1499.77` (-0.008504)
- EV windows improved/regressed: `0/3`
- PnL windows improved/regressed: `0/3`
- MRVL trades/PnL: `5` / `$789.88`

## Production impact

```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
```

## Decision rationale

MRVL-only candidate expansion did not produce robust three-window EV improvement.

Next evidence needed: If kept under watch, validate with point-in-time candidate selection or a live pilot sleeve before any production universe change.
