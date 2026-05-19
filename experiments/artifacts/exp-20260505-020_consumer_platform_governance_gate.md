# exp-20260505-020 Consumer Platform Governance Gate

Decision: `rejected`
Best variant: `risk_on_only`

## Aggregate

- EV delta sum: `+0.0557` (+1.09%)
- PnL delta sum: `$+8,024.56` (+5.11%)
- EV windows improved/regressed: `1` / `2`
- Candidate/passed/zeroed signals: `10` / `10` / `0`

## Three-window best deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | -0.2570 | -3211.76 | -0.16 | +0.0000 | -0.0357 | +1 | 1 | -1796.95 |
| mid_weak | +0.4803 | +19182.11 | -0.03 | +0.0022 | +0.0671 | +1 | 2 | +15886.33 |
| old_thin | -0.1676 | -7945.79 | -0.39 | +0.0276 | -0.0891 | +3 | 4 | -1120.96 |

## Parity

No production universe or order path changed in this replay. If accepted, promotion must use a shared universe-governance gate or default-off pilot path so run.py and backtester.py consume the same rule.
