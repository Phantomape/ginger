# exp-20260522-018 Low-deployment ETF Momentum Lead

Decision: `rejected_low_deployment_etf_momentum_lead`
Best variant: `lead_50bp`

## Hypothesis

On idle-capital days, the accepted low-deployment ETF overlay may perform better when raw momentum leadership is unambiguous. Requiring the selected ETF to lead the second-best eligible ETF by a minimum prior-20d momentum spread could improve replacement value and reduce rotation noise without changing the pool or notional.

## Variant Sweep

| Variant | Min lead | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| lead_25bp | 0.0025 | +0.1042 | $+1,114.49 | 2/1 | 2/1 | +0.0004 | 125 | FAIL |
| lead_50bp | 0.0050 | +0.3137 | $+3,364.15 | 2/1 | 2/1 | -0.0001 | 118 | FAIL |
| lead_75bp | 0.0075 | +0.2876 | $+2,773.76 | 2/1 | 2/1 | -0.0001 | 114 | FAIL |
| lead_100bp | 0.0100 | -0.0261 | $-2,343.79 | 1/2 | 1/2 | +0.0006 | 110 | FAIL |
| lead_150bp | 0.0150 | +0.0166 | $-1,773.66 | 1/2 | 1/2 | +0.0006 | 102 | FAIL |
| lead_200bp | 0.0200 | +0.0914 | $-1,026.56 | 1/2 | 1/2 | +0.0003 | 97 | FAIL |
| lead_300bp | 0.0300 | -0.1981 | $-7,088.41 | 1/2 | 0/3 | +0.0035 | 76 | FAIL |

## Best Variant Three-window Deltas Vs Accepted v1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta | Ticker days |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | +0.2773 | $+2,939.27 | +0.0294 | +0.12 | -0.0012 | -5 | GLD:6, IWM:7, QQQ:4, SLV:24 |
| mid_weak | +0.0467 | $+782.14 | +0.0078 | +0.03 | -0.0001 | -3 | GLD:13, IWM:1, QQQ:14, SLV:8 |
| old_thin | -0.0103 | $-357.26 | -0.0036 | -0.01 | -0.0013 | -6 | GLD:20, QQQ:7, SLV:14 |

## Aggregate

- EV delta vs v1: `0.3137` (`0.037709`)
- PnL delta vs v1: `$3364.15` (`0.013718`)
- EV windows improved/regressed: `2` / `1`
- PnL windows improved/regressed: `2` / `1`
- max DD delta max: `-0.0001`

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, momentum-lead variants measured against accepted raw-momentum v1 low-deployment ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, at least 4 overlay days in each window, and at least 2% aggregate EV or PnL uplift versus accepted v1.",
  "single_ticker_positive_share": 0.519,
  "strong_materiality_passed": true
}
```

## Decision Rationale

No momentum-lead variant beat the accepted raw-momentum v1 overlay across the three-window EV/PnL/drawdown/concentration gate.

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

Live/default orders remain unchanged.
