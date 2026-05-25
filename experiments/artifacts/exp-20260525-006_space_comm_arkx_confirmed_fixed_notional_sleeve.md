# exp-20260525-006 Space Comm ARKX-Confirmed Fixed-Notional Sleeve

Decision: `rejected_space_comm_arkx_confirmed_fixed_notional_sleeve`.

Single variable: route the fixed governed Space communications/satcom cohort into an additive fixed-notional default-off paper sleeve only when prior-close ARKX 20d momentum is at least equal to SPY.

## Trial Accounting

- trial_family: `governed_space_comm_arkx_confirmed_fixed_notional_paper_sleeve`
- changed_variable: `space_comm_arkx_confirmed_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `free_same_theme_arkx_prior_close_market_confirmation_for_governed_space_comm_candidate_pool`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.8077 | -0.1277 | $113,719.84 | $112,329.37 | $-1,390.47 | +0.0003 | 3 | 4 |
| mid_weak | 2.1386 | 2.4578 | +0.3192 | $78,050.31 | $84,166.19 | $+6,115.88 | -0.0022 | 5 | 1 |
| old_thin | 0.5805 | 0.5510 | -0.0295 | $40,307.27 | $39,082.32 | $-1,224.95 | +0.0009 | 2 | 1 |

## Aggregate

- EV delta: `0.162` (`0.021164`)
- PnL delta: `$3500.46` (`0.015083`)
- target trades: `10` across `3` windows
- max single positive share: `0.69989`
- positive PnL HHI: `0.579912`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0009,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.69989,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.579912,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 10,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
