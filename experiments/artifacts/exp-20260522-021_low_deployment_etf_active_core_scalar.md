# exp-20260522-021 Low-deployment ETF Active-Core Scalar

Decision: `rejected_low_deployment_etf_active_core_scalar`
Best variant: `active_core_one_150`

## Hypothesis

The accepted low-deployment ETF overlay may have different replacement value when the core book already has one active A/B position versus zero. Scaling only the active-core-one paper notional tests capital competition without changing the ETF selector, pool, activation threshold, or core behavior.

## Trial Accounting

- trial_family: `low_deployment_dynamic_etf_overlay_capital_competition`
- changed_variable: `low_deployment_etf_overlay_active_core_one_notional_scalar`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `new_production_visible_field`

## Variant Sweep

| Variant | active=1 scalar | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| active_core_one_000 | 0.00 | -0.1496 | $-8,972.82 | 1/2 | 0/3 | +0.0028 | 132 | FAIL |
| active_core_one_025 | 0.25 | -0.0796 | $-6,729.62 | 1/2 | 0/3 | +0.0021 | 132 | FAIL |
| active_core_one_050 | 0.50 | -0.0368 | $-4,486.42 | 1/2 | 0/3 | +0.0014 | 132 | FAIL |
| active_core_one_075 | 0.75 | -0.0085 | $-2,243.20 | 1/2 | 0/3 | +0.0007 | 132 | FAIL |
| active_core_one_125 | 1.25 | +0.0010 | $+2,243.20 | 2/1 | 3/0 | +0.0010 | 132 | FAIL |
| active_core_one_150 | 1.50 | +0.0032 | $+4,486.41 | 2/1 | 3/0 | +0.0021 | 132 | FAIL |

## Best Variant Three-window Deltas Vs Accepted v1

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | active-count split | Ticker days |
|---|---:|---:|---:|---:|---:|---|---|
| late_strong | -0.1421 | $+627.04 | +0.0063 | -0.14 | +0.0015 | 0:19, 1:27 | GLD:7, IWM:7, QQQ:5, SLV:25, SPY:2 |
| mid_weak | +0.0829 | $+1,747.50 | +0.0175 | +0.04 | -0.0013 | 0:18, 1:21 | GLD:13, IWM:2, QQQ:14, SLV:9, SPY:1 |
| old_thin | +0.0624 | $+2,111.87 | +0.0211 | +0.06 | +0.0021 | 0:28, 1:19 | GLD:25, QQQ:8, SLV:14 |

## Aggregate

- EV delta vs v1: `0.0032` (`0.000385`)
- PnL delta vs v1: `$4486.41` (`0.018295`)
- EV windows improved/regressed: `2` / `1`
- PnL windows improved/regressed: `3` / `0`
- max DD delta max: `0.0021`

## Gate 4

```json
{
  "basis": "Three canonical backtesting.md windows, active-core-one notional variants measured against accepted raw-momentum v1 low-deployment ETF overlay.",
  "concentration_ok": true,
  "passed": false,
  "passed_directionally": false,
  "rule": "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive contribution share <= 75%, at least 4 overlay days in each window, and at least 2% aggregate EV or PnL uplift versus accepted v1.",
  "single_ticker_positive_share": 0.4979,
  "strong_materiality_passed": false
}
```

## Decision Rationale

No active-core-one notional scalar beat the accepted raw-momentum v1 overlay across the three-window EV/PnL/drawdown/materiality gate.

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

No JavaScript was used.
