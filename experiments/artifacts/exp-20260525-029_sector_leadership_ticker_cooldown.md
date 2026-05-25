# exp-20260525-029 Sector-Leadership Ticker-Cooldown

Decision: `rejected_sector_leadership_ticker_cooldown`.

Single variable: keep the exp-20260525-916 sector-leadership source fixed, but skip same-ticker candidates selected by this source during the prior 10 trading days.

## Trial Accounting

- trial_family: `sector_leadership_ticker_crowding_cooldown_paper_sleeve`
- changed_variable: `sector_leadership_same_ticker_10d_cooldown_v1`
- prior_trial_count: `1`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `production_visible_source_crowding_field_derived_from_rejected_raw_sector_leadership_tail_failure`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.6713 | -0.4915 | $117,072.92 | $113,379.35 | $-3,693.57 | +0.0037 | 48 | 366 |
| mid_weak | 2.1402 | 4.3058 | +2.1656 | $78,110.11 | $111,842.93 | $+33,732.82 | -0.0141 | 99 | 843 |
| old_thin | 0.5911 | 0.5905 | -0.0006 | $39,667.96 | $38,853.96 | $-814.00 | +0.0520 | 69 | 511 |

## Aggregate

- EV delta: `1.6735` (`0.211994`)
- PnL delta: `$29225.25` (`0.124442`)
- target trades: `216` across `3` windows
- max single positive share: `0.139158`
- positive PnL HHI: `0.083544`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_checks": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.052,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.139158,
    "max_single_positive_pnl_share_guardrail": 0.35,
    "passed": true,
    "positive_pnl_hhi": 0.083544,
    "positive_pnl_hhi_guardrail": 0.25
  },
  "target_trade_count": 216,
  "target_trade_count_min": 60,
  "target_window_count_min": 3,
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
