# exp-20260528-033 AI Optical Low Close-Location Support

Decision: `rejected_ai_optical_low_close_location_notional_support`.

Single variable: apply a 1.10x fixed-notional paper scalar only to accepted AI optical IWM-confirmed paper trades whose target ticker signal-day close location is <= 0.60.

## Trial Accounting

- trial_family: `ai_optical_signal_day_low_close_location_support`
- trial_variant_id: `close_location_lte_0p60_scalar_1p10_v1`
- changed_variable: `ai_optical_signal_day_low_close_location_notional_scalar_v1`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `free_ohlcv_signal_day_close_location_field_on_governed_optical_pool`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Supported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6.5333 | 6.5586 | +0.0253 | $139,904.00 | $140,143.50 | $+239.50 | -0.0001 | 1 |
| mid_weak | 2.7906 | 2.8012 | +0.0106 | $92,096.06 | $92,447.56 | $+351.50 | +0.0000 | 2 |
| old_thin | 0.2242 | 0.2242 | +0.0000 | $20,200.09 | $20,200.09 | $+0.00 | +0.0000 | 0 |

## Aggregate

- EV delta: `0.0359` (`0.00376`)
- PnL delta: `$591.0` (`0.002343`)
- supported trades: `3` across `2` windows
- before target trades: `10`
- after target trades: `10`
- max single positive share: `0.316761`
- positive PnL HHI: `0.271779`

## Gate 4

```json
{
  "after_target_trade_count": 10,
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "before_target_trade_count": 10,
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "supported_trade_count": 3,
  "supported_trade_count_min": 4,
  "supported_window_count_min": 2,
  "supported_windows": [
    "late_strong",
    "mid_weak"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.316761,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.271779,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

Rejection reason: `supported_sample_too_small`.

No JavaScript was used.
