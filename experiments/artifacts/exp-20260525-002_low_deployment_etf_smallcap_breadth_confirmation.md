# exp-20260525-002 Low-deployment ETF Small-cap Breadth Confirmation

Decision: `rejected_low_deployment_etf_smallcap_breadth_confirmation`
Best variant: `iwm_lag_max_250bp`

## Hypothesis

On idle-capital days, the accepted low-deployment ETF overlay may perform better when cap-weight momentum is confirmed by small-cap breadth. Requiring IWM prior-20d momentum to avoid lagging SPY by more than a fixed spread could improve replacement value without changing the ETF pool, notional, or core stock slot logic.

## Variant Sweep

| Variant | IWM-SPY min spread | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| iwm_lag_max_500bp | -0.0500 | +0.1086 | $+1,269.47 | 2/0 | 2/0 | +0.0000 | 124 | FAIL |
| iwm_lag_max_250bp | -0.0250 | +0.4230 | $+435.61 | 1/1 | 1/1 | +0.0007 | 100 | FAIL |
| iwm_lag_max_100bp | -0.0100 | +0.3439 | $-2,057.25 | 1/2 | 1/2 | +0.0019 | 71 | FAIL |
| iwm_not_lagging | +0.0000 | +0.3526 | $-679.36 | 1/2 | 1/2 | +0.0023 | 48 | FAIL |
| iwm_leads_100bp | +0.0100 | +0.2775 | $+1,184.79 | 2/1 | 2/1 | +0.0028 | 26 | FAIL |
| iwm_leads_250bp | +0.0250 | -0.1890 | $-4,224.27 | 1/2 | 1/2 | +0.0033 | 14 | FAIL |

## Best Variant Three-window Deltas Vs Accepted v1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta | Ticker days |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | +0.5802 | $+6,274.25 | +0.0628 | +0.24 | +0.0004 | -12 | GLD:7, IWM:7, QQQ:4, SLV:16 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 | +0.00 | +0.0000 | +0 | GLD:13, IWM:2, QQQ:14, SLV:9, SPY:1 |
| old_thin | -0.1572 | $-5,838.64 | -0.0584 | -0.16 | +0.0007 | -20 | GLD:14, QQQ:1, SLV:12 |

## Aggregate

- EV delta vs v1: `0.423` (`0.050847`)
- PnL delta vs v1: `$435.61` (`0.001776`)
- EV windows improved/regressed: `1` / `1`
- PnL windows improved/regressed: `1` / `1`
- max DD delta max: `0.0007`

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, small-cap breadth variants measured against accepted raw-momentum v1 low-deployment ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, at least 4 overlay days in each window, and at least 2% aggregate EV or PnL uplift versus accepted v1.",
  "single_ticker_positive_share": 0.5174,
  "strong_materiality_passed": true
}
```

## Decision Rationale

No IWM-minus-SPY breadth confirmation variant beat the accepted raw-momentum v1 overlay across the three-window EV/PnL/drawdown/concentration gate.

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
