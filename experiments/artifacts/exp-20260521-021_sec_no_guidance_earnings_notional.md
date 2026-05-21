# exp-20260521-021 SEC no-guidance earnings notional

## Hypothesis
Earnings-release filings that explicitly decline, suspend, or withhold guidance are a distinct continuation-quality cohort in the SEC financial-report paper sleeve.

## Trial accounting
- trial_family: sec_earnings_guidance_nonresponse_semantic_field
- changed_variable: no_guidance_earnings_notional_scalar
- prior_trial_count: 3 nearby SEC earnings-release semantic notional scouts
- nearby_prior_experiments: exp-20260516-034, exp-20260520-013, exp-20260520-015
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_sec_text_semantic_field

## Gate
- decision: rejected_sec_no_guidance_earnings_notional
- gate_passed: False
- selected_variant: no_guidance_scalar_0_70
- rejection_reason: No no-guidance earnings-release scalar cleared the three-window, tail-aware paper-sleeve gate on top of the accepted SEC stack.
- checks: {"adjusted_trade_sample": false, "adjusted_window_coverage": false, "drawdown_worse_guard": true, "ev_improved_window_coverage": false, "hhi_concentration_cap": true, "no_ev_regressed_windows": true, "positive_aggregate_ev": false, "positive_aggregate_pnl": false, "single_ticker_positive_share_cap": true, "top5_contribution_cap": true}

## Target coverage
- target_candidate_rows: 0
- target_share: 0.0
- target_tickers: {}
- pattern_counts: {}

## Selected metrics
```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.0,
    "expected_value_score_sum_delta_pct": 0.0,
    "max_drawdown_pct_max_delta": 0.0,
    "max_drawdown_pct_max_delta_pct": 0.0,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 0.0,
    "sleeve_total_pnl_sum_delta_pct": 0.0,
    "total_pnl_sum_delta": 0.0,
    "total_pnl_sum_delta_pct": 0.0,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "mid_weak": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    }
  },
  "ev_positive_windows": 0,
  "ev_regressed_windows": 0,
  "max_drawdown_delta_max": 0.0,
  "no_guidance_earnings_notional_scalar": 0.7,
  "pnl_positive_windows": 0,
  "pnl_regressed_windows": 0
}
```

## Production impact
No shared policy or live adapter changed. This is an offline paper-sleeve scout; promotion would require shared policy wiring and parity tests.
