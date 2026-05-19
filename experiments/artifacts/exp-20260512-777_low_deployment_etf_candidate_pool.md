# exp-20260512-777 Low-deployment ETF Candidate Pool

Decision: `rejected_keep_v1_candidate_pool`

## Hypothesis

The accepted low-deployment ETF overlay may improve replacement value if its candidate pool includes only the most useful liquid macro ETF surfaces, rather than blindly keeping the original v1 set.

## Best Variant Versus Accepted V1

- best_variant: `v1_current`
- candidate_pool: `['QQQ', 'SPY', 'IWM', 'GLD', 'SLV']`
- EV delta vs v1: `0.0`
- PnL delta vs v1: `$0.0`
- EV windows improved/regressed: `0` / `0`
- PnL windows improved/regressed: `0` / `0`
- max DD delta max: `0.0`

## Three-window Deltas Vs V1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 |
| old_thin | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 |

## Variant Summary

| Variant | Pool | EV delta vs v1 | PnL delta vs v1 | EV +/- windows | Gate 4 |
|---|---|---:|---:|---:|---|
| v1_current | QQQ, SPY, IWM, GLD, SLV | +0.0000 | $+0.00 | 0/0 | False |
| no_slv | QQQ, SPY, IWM, GLD | -0.3783 | $-4,341.11 | 1/2 | False |
| metals_only | GLD, SLV | -0.4299 | $-9,023.14 | 0/3 | False |
| gold_only | GLD | -0.7997 | $-14,617.12 | 0/3 | False |
| equity_only | QQQ, SPY, IWM | +0.3375 | $+3,158.15 | 2/1 | False |
| add_bonds | QQQ, SPY, IWM, GLD, SLV, TLT, IEF | -0.2239 | $-4,344.90 | 0/3 | False |
| add_energy | QQQ, SPY, IWM, GLD, SLV, USO, XLE | +0.6600 | $+9,133.28 | 1/1 | False |
| cross_asset_plus | QQQ, SPY, IWM, GLD, SLV, TLT, IEF, USO, XLE | +0.5014 | $+5,582.88 | 1/2 | False |
| defensive_plus | GLD, SLV, TLT, IEF, UUP | -0.4190 | $-8,918.41 | 0/3 | False |

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, candidate-pool delta measured against accepted v1 ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, and at least 2% aggregate EV or PnL uplift versus the accepted overlay baseline.",
  "single_ticker_positive_share": 0.5024,
  "strong_materiality_passed": false
}
```

## Decision Rationale

No tested ETF candidate-pool variant beat the accepted v1 pool across the three-window EV/PnL/drawdown/concentration gate.

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
