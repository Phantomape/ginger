# exp-20260528-026 Space Trend High-Close Fixed-Notional Sleeve

Decision: `accepted_default_off_space_trend_high_close_fixed_notional_sleeve`.

Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when the existing signal engine labels the discovery `trend_long` and signal-day close-location is `>= 0.84`.

## Gate Questions

- alpha_hypothesis: entry/candidate_pool/risk allocation: governed full-history Space trend_long candidates may produce additive replacement value when the signal day closes in the top 16% of its intraday range.
- single_causal_variable: `space_governed_trend_high_close_fixed_notional_paper_sleeve_routing_v1`
- reproducibility: `.venv\Scripts\python.exe quant\experiments\exp_20260528_026_space_trend_high_close_fixed_notional_sleeve.py`

## Trial Accounting

- trial_family: `governed_space_trend_high_close_fixed_notional_paper_sleeve`
- changed_variable: `space_governed_trend_high_close_fixed_notional_paper_sleeve_routing_v1`
- prior_trial_count: `11`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `orthogonal_free_ohlcv_signal_day_close_location_field_on_governed_space_trend_candidate_pool`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5755 | 4.7332 | +0.1577 | $109,198.53 | $111,371.18 | $+2,172.65 | +0.0000 | 1 | 8 |
| mid_weak | 2.6219 | 3.2147 | +0.5928 | $88,276.19 | $98,612.40 | $+10,336.21 | -0.0021 | 5 | 2 |
| old_thin | 0.3787 | 0.3787 | +0.0000 | $28,472.77 | $28,472.77 | $+0.00 | +0.0000 | 0 | 4 |

## Aggregate

- EV delta: `0.7505` (`0.099062`)
- PnL delta: `$12508.86` (`0.055362`)
- target trades: `6` across `2` windows
- max single positive share: `0.353561`
- positive PnL HHI: `0.27265`

## Gate 4

```json
{
  "acceptance_rule": "positive aggregate EV/PnL; zero EV/PnL-regressed windows; >=6 target trades across >=2 windows; drawdown drift <=0.5pp; survival >=5%; concentration guard passes",
  "aggregate_ev_delta_positive": true,
  "aggregate_expected_value_score_delta": 0.7505,
  "aggregate_pnl_delta_positive": true,
  "aggregate_total_pnl_delta": 12508.86,
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.353561,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.27265,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Gate-passing metadata is surfaced through the shared feature layer and default-off Space observation slot. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
