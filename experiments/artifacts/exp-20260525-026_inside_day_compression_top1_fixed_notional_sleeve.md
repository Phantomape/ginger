# exp-20260525-026 Inside-Day Compression Top-1 Fixed-Notional Sleeve

Decision: `rejected_inside_day_compression_top1_fixed_notional_sleeve`.

Single variable: a default-off paper sleeve admits at most one inside-day compression breakout candidate per day, enters at next open, and exits after ten trading days.

## Trial Accounting

- trial_family: `inside_day_compression_breakout_default_off_paper_sleeve`
- changed_variable: `inside_day_compression_top1_next_open_10d_fixed_notional_sleeve_v1`
- prior_trial_count: `1`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `current_three_window_next_open_slippage_adjusted_fixed_notional_paper_sleeve_replay`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.5399 | -0.6229 | $117,072.92 | $108,613.86 | $-8,459.06 | +0.0013 | 47 | 99 |
| mid_weak | 2.1402 | 2.8122 | +0.6720 | $78,110.11 | $91,006.20 | $+12,896.09 | -0.0058 | 64 | 128 |
| old_thin | 0.5911 | 0.3819 | -0.2092 | $39,667.96 | $31,053.00 | $-8,614.96 | +0.0332 | 60 | 117 |

## Aggregate

- EV delta: `-0.1601` (`-0.020281`)
- PnL delta: `$-4177.93` (`-0.01779`)
- target trades: `171` across `3` windows
- max single positive share: `0.213487`
- positive PnL HHI: `0.130621`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "max_drawdown_worse": 0.0332,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.213487,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.130621,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 171,
  "target_trade_count_min": 20,
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
