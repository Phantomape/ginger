# exp-20260525-007 Consumer Platform QQQ-Confirmed Fixed-Notional Sleeve

Decision: `rejected_consumer_platform_qqq_confirmed_fixed_notional_sleeve`.

Single variable: route the fixed governed consumer digital platform cohort into an additive fixed-notional default-off paper sleeve only when prior-close QQQ 20d momentum is at least equal to SPY.

## Trial Accounting

- trial_family: `governed_consumer_platform_qqq_confirmed_fixed_notional_paper_sleeve`
- changed_variable: `consumer_platform_qqq_confirmed_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `moderate_high`
- new_evidence_type: `production_visible_qqq_spy_growth_confirmation_plus_fixed_notional_sleeve_routing_for_existing_governed_consumer_platform_cohort`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.8321 | -0.1033 | $113,719.84 | $112,901.25 | $-818.59 | +0.0004 | 1 | 0 |
| mid_weak | 2.1386 | 2.2204 | +0.0818 | $78,050.31 | $79,872.41 | $+1,822.10 | +0.0000 | 1 | 0 |
| old_thin | 0.5805 | 0.5819 | +0.0014 | $40,307.27 | $40,412.54 | $+105.27 | +0.0000 | 4 | 0 |

## Aggregate

- EV delta: `-0.0201` (`-0.002626`)
- PnL delta: `$1108.78` (`0.004778`)
- target trades: `6` across `3` windows
- max single positive share: `0.532882`
- positive PnL HHI: `0.502162`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0004,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.532882,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.502162,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
