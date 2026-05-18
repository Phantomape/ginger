# exp-20260518-003 Low-deployment ETF Activation Threshold

Decision: `rejected_keep_v1_activation_threshold`

## Hypothesis

The accepted low-deployment ETF overlay may have better replacement value if its activation threshold is calibrated to the amount of core book deployment, rather than assuming <=1 active core position is the only useful idle-capital state.

## Best Variant Versus Accepted <=1

- best_variant: `v1_current_le1`
- max_active_core_positions: `1`
- EV delta vs <=1: `0.0`
- PnL delta vs <=1: `$0.0`
- EV windows improved/regressed: `0` / `0`
- PnL windows improved/regressed: `0` / `0`
- max DD delta max: `0.0`

## Three-window Deltas Vs <=1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 |
| old_thin | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 |

## Variant Summary

| Variant | Max active core | EV delta vs <=1 | PnL delta vs <=1 | EV +/- windows | Gate 4 | Overlay days |
|---|---:|---:|---:|---:|---|---:|
| zero_only | 0 | -0.1496 | $-8,972.82 | 1/2 | False | 65 |
| v1_current_le1 | 1 | +0.0000 | $+0.00 | 0/0 | False | 132 |
| moderate_le2 | 2 | -0.5526 | $-8,277.56 | 0/3 | False | 211 |
| loose_le3 | 3 | -1.8742 | $-25,886.10 | 0/3 | False | 268 |
| very_loose_le4 | 4 | -1.8754 | $-32,354.45 | 0/3 | False | 321 |

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, activation-threshold delta measured against the accepted <=1 low-deployment ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus <=1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, at least 4 overlay days in each window, and at least 2% aggregate EV or PnL uplift versus the accepted overlay baseline.",
  "single_ticker_positive_share": 0.5024,
  "strong_materiality_passed": false
}
```

## Decision Rationale

No tested max_active_core_positions variant beat the accepted <=1 low-deployment ETF overlay across the three-window EV/PnL/drawdown/concentration gate.

## Production Impact

```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
  default_off_paper_only: True
  alters_orders: False
```

Live/default orders remain disabled.
