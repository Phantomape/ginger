# exp-20260522-004 Low-deployment ETF Volatility Cap

Decision: `rejected_low_deployment_etf_volatility_cap`
Best variant: `vol_cap_250bp`

## Hypothesis

On idle-capital days, the accepted low-deployment ETF overlay may be overpaying for high-volatility acceleration. Filtering overlay ETF candidates by prior 20-day realized volatility could preserve raw momentum replacement value while reducing drawdown and tail exposure.

## Variant Sweep

| Variant | Cap | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| vol_cap_125bp | 0.0125 | +0.0012 | $+950.19 | 2/1 | 3/0 | +0.0028 | 90 | FAIL |
| vol_cap_150bp | 0.0150 | +0.1001 | $+3,778.68 | 2/1 | 2/1 | +0.0030 | 103 | FAIL |
| vol_cap_200bp | 0.0200 | +0.1463 | $+3,168.50 | 3/0 | 3/0 | +0.0030 | 122 | FAIL |
| vol_cap_250bp | 0.0250 | +0.4939 | $+6,864.16 | 2/0 | 2/0 | +0.0000 | 130 | FAIL |
| vol_cap_300bp | 0.0300 | +0.2376 | $+2,883.28 | 1/0 | 1/0 | +0.0000 | 131 | FAIL |
| vol_cap_400bp | 0.0400 | +0.2376 | $+2,883.28 | 1/0 | 1/0 | +0.0000 | 131 | FAIL |

## Best Variant Three-window Deltas Vs Accepted v1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta | Ticker days |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | +0.4519 | $+5,968.94 | +0.0597 | +0.15 | -0.0002 | -2 | GLD:12, IWM:8, QQQ:5, SLV:17, SPY:2 |
| mid_weak | +0.0420 | $+895.22 | +0.0090 | +0.02 | +0.0000 | +0 | GLD:14, IWM:2, QQQ:14, SLV:8, SPY:1 |
| old_thin | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 | GLD:25, QQQ:8, SLV:14 |

## Aggregate

- EV delta vs v1: `0.4939` (`0.05937`)
- PnL delta vs v1: `$6864.16` (`0.027991`)
- EV windows improved/regressed: `2` / `0`
- PnL windows improved/regressed: `2` / `0`
- max DD delta max: `0.0`

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, volatility-cap variants measured against accepted raw-momentum v1 low-deployment ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, at least 4 overlay days in each window, and at least 2% aggregate EV or PnL uplift versus accepted v1.",
  "single_ticker_positive_share": 0.457,
  "strong_materiality_passed": true
}
```

## Decision Rationale

No volatility-cap variant beat the accepted raw-momentum v1 overlay across the three-window EV/PnL/drawdown/concentration gate.

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
