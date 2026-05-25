# exp-20260525-901 Opening-Range Macro-Confirmed Quality Gate

Decision: `rejected_opening_range_macro_confirmed_quality_gate`.

Single variable: route the existing non-Tech/orderly opening-range daily top-1 source into default-off paper only when SPY has outperformed both TLT and UUP over the prior 20 trading days.

## Trial Accounting

- trial_family: `opening_range_continuation_macro_confirmed_paper_sleeve`
- changed_variable: `opening_range_top1_nontech_orderly_macro_confirmation_v1`
- prior_trial_count: `2`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `orthogonal_cross_asset_macro_confirmation_field`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target | Macro rejected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2785 | +0.1157 | $117,072.92 | $117,301.90 | $+228.98 | -0.0003 | 16 | 11 |
| mid_weak | 2.1402 | 2.1553 | +0.0151 | $78,110.11 | $78,087.76 | $-22.35 | -0.0011 | 22 | 5 |
| old_thin | 0.5911 | 0.7529 | +0.1618 | $39,667.96 | $45,627.63 | $+5,959.67 | -0.0095 | 11 | 18 |

## Aggregate

- EV delta: `0.2926` (`0.037066`)
- PnL delta: `$6166.3` (`0.026256`)
- target trades: `49` across `3` windows
- max single positive share: `0.294798`
- positive PnL HHI: `0.174033`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": -0.0003,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.294798,
    "max_single_positive_pnl_share_guardrail": 0.35,
    "passed": true,
    "positive_pnl_hhi": 0.174033,
    "positive_pnl_hhi_guardrail": 0.25
  },
  "target_trade_count": 49,
  "target_trade_count_min": 45,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
