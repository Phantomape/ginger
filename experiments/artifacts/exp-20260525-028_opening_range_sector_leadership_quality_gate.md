# exp-20260525-028 Opening-Range Sector-Leadership Quality Gate

Decision: `rejected_opening_range_sector_leadership_quality_gate`.

Single variable: route the existing non-Tech/orderly opening-range daily top-1 source into default-off paper only when its sector is a top-three 20d sector-median leader and is beating SPY.

## Trial Accounting

- trial_family: `opening_range_continuation_sector_leadership_paper_sleeve`
- changed_variable: `opening_range_top1_nontech_orderly_sector_leadership_v1`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `orthogonal_sector_median_leadership_confirmation_field`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target | Sector rejected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3398 | +0.1770 | $117,072.92 | $118,403.00 | $+1,330.08 | -0.0003 | 14 | 13 |
| mid_weak | 2.1402 | 2.1031 | -0.0371 | $78,110.11 | $77,319.22 | $-790.89 | -0.0006 | 10 | 17 |
| old_thin | 0.5911 | 0.7763 | +0.1852 | $39,667.96 | $46,205.98 | $+6,538.02 | +0.0034 | 17 | 12 |

## Aggregate

- EV delta: `0.3251` (`0.041183`)
- PnL delta: `$7077.21` (`0.030135`)
- target trades: `41` across `3` windows
- max single positive share: `0.31563`
- positive PnL HHI: `0.173004`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0034,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.31563,
    "max_single_positive_pnl_share_guardrail": 0.35,
    "passed": true,
    "positive_pnl_hhi": 0.173004,
    "positive_pnl_hhi_guardrail": 0.25
  },
  "target_trade_count": 41,
  "target_trade_count_min": 45,
  "target_window_count_min": 3,
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
