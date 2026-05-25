# exp-20260525-004 Compute-Memory Fixed-Notional Sleeve

Decision: `rejected_compute_memory_fixed_notional_sleeve`.

Single variable: route governed INTC/WDC/STX compute-memory/storage target trades into an additive fixed-notional default-off paper sleeve.

## Trial Accounting

- trial_family: `governed_compute_memory_fixed_notional_paper_sleeve`
- changed_variable: `compute_memory_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `7`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `candidate_pool_capital_routing_no_displacement_fixed_notional_for_existing_governed_compute_memory_cohort`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.9149 | -0.0205 | $113,719.84 | $114,300.62 | $+580.78 | -0.0003 | 3 |
| mid_weak | 2.1386 | 2.2853 | +0.1467 | $78,050.31 | $81,040.65 | $+2,990.34 | +0.0000 | 2 |
| old_thin | 0.5805 | 0.5703 | -0.0102 | $40,307.27 | $39,883.48 | $-423.79 | +0.0003 | 1 |

## Aggregate

- EV delta: `0.116` (`0.015154`)
- PnL delta: `$3147.33` (`0.013562`)
- target trades: `6` across `3` windows
- max single positive share: `0.551575`
- positive PnL HHI: `0.431349`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0003,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.551575,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.431349,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
  "target_trade_count_min": 6,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
