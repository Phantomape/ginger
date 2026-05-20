# exp-20260520-016 Low-deployment Risk-adjusted ETF Selector

Decision: `rejected_low_deployment_risk_adjusted_selector`

## Hypothesis

The accepted low-deployment ETF overlay currently picks the highest raw prior 20-day momentum ETF. On idle-capital days, a risk-adjusted momentum selector may improve replacement value by preferring cleaner persistence over volatile acceleration while keeping the same ETF pool, activation threshold, notional, and paper-only execution.

## Three-window Deltas Vs Accepted v1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta | Ticker days |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | +0.0209 | $+202.48 | +0.0020 | +0.01 | -0.0002 | +0 | GLD:10, IWM:7, QQQ:5, SLV:21, SPY:3 |
| mid_weak | +0.1988 | $+4,001.59 | +0.0400 | +0.10 | +0.0006 | +0 | GLD:15, IWM:1, QQQ:14, SLV:4, SPY:5 |
| old_thin | -0.0249 | $-714.32 | -0.0072 | -0.03 | +0.0001 | +0 | GLD:32, QQQ:7, SLV:3, SPY:5 |

## Aggregate

- EV delta vs v1: `0.1948` (`0.023416`)
- PnL delta vs v1: `$3489.75` (`0.014231`)
- EV windows improved/regressed: `2` / `1`
- PnL windows improved/regressed: `2` / `1`
- max DD delta max: `0.0006`

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, risk-adjusted selector delta measured against accepted raw-momentum v1 low-deployment ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, at least 4 overlay days in each window, and at least 2% aggregate EV or PnL uplift versus accepted v1.",
  "single_ticker_positive_share": 0.375,
  "strong_materiality_passed": true
}
```

## Decision Rationale

The risk-adjusted selector did not beat the accepted raw-momentum v1 overlay across the three-window EV/PnL/drawdown/concentration gate.

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
