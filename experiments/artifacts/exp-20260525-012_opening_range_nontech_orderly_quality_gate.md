# exp-20260525-012 Opening-Range Non-Tech Orderly Quality Gate

Decision: `rejected_opening_range_nontech_orderly_quality_gate`.

Single variable: keep the existing opening-range daily top-1 source, but route it into default-off paper only when the selected candidate is non-Technology and has an orderly signal-day/gap path.

## Trial Accounting

- trial_family: `opening_range_continuation_quality_gated_paper_sleeve`
- changed_variable: `opening_range_top1_nontech_orderly_quality_gate_v1`
- prior_trial_count: `1`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `production_visible_return_path_cluster_quality_gate_on_existing_opening_range_top1_source`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target | Rejected top1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4530 | +0.2902 | $117,072.92 | $120,109.27 | $+3,036.35 | +0.0004 | 27 | 32 |
| mid_weak | 2.1402 | 2.3478 | +0.2076 | $78,110.11 | $81,517.30 | $+3,407.19 | -0.0020 | 27 | 49 |
| old_thin | 0.5911 | 0.6413 | +0.0502 | $39,667.96 | $41,638.79 | $+1,970.83 | +0.0059 | 29 | 43 |

## Aggregate

- EV delta: `0.548` (`0.069419`)
- PnL delta: `$8414.37` (`0.035829`)
- target trades: `83` across `3` windows
- max single positive share: `0.18097`
- positive PnL HHI: `0.116462`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0059,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.18097,
    "max_single_positive_pnl_share_guardrail": 0.35,
    "passed": true,
    "positive_pnl_hhi": 0.116462,
    "positive_pnl_hhi_guardrail": 0.25
  },
  "target_trade_count": 83,
  "target_trade_count_min": 60,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
