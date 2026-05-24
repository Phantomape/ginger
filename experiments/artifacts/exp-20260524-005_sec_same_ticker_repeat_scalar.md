# exp-20260524-005 SEC Same-Ticker Repeat Scalar

Decision: `rejected_sec_same_ticker_repeat_scalar`.

## Hypothesis

Within the default-off SEC financial-report paper sleeve, repeated same-ticker entries inside a 60-calendar-day lookback may represent a distinct replacement-value state. A bounded paper-notional scalar can test whether that state should be faded for concentration control or expanded for continuation value without changing eligibility, ranking, exits, LLM authority, or live orders.

## Best Variant

- best_variant: `repeat_scalar_2_00`
- target_scalar: `2.0`
- EV delta: `0.673494`
- PnL delta: `$13494.04`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 |
| mid_weak | +0.6058 | $+9,784.71 | -0.0023 |
| old_thin | +0.0677 | $+3,709.33 | +0.0026 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.673494,
    "expected_value_score_sum_delta_pct": 0.05677,
    "max_drawdown_pct_max_delta": 0.002618,
    "max_drawdown_pct_max_delta_pct": 0.022382,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 13494.04,
    "sleeve_total_pnl_sum_delta_pct": 0.154503,
    "total_pnl_sum_delta": 13494.04,
    "total_pnl_sum_delta_pct": 0.041618,
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
      "expected_value_score": 0.605794,
      "max_drawdown_pct": -0.00231,
      "sharpe_daily": 0.196106,
      "total_pnl": 9784.71
    },
    "old_thin": {
      "expected_value_score": 0.0677,
      "max_drawdown_pct": 0.002618,
      "sharpe_daily": -0.014509,
      "total_pnl": 3709.33
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 7,
    "adjusted_windows": [
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.002618,
    "max_single_positive_pnl_share": 0.6214,
    "pnl_hhi_concentration": 0.5295,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 2,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
    "sample_guard": {
      "min_adjusted_trades": 6,
      "min_adjusted_windows": 2
    },
    "tail_guard": {
      "max_hhi_concentration": 0.35,
      "max_single_ticker_positive_share": 0.5,
      "max_top5_contribution": 0.6
    }
  }
}
```

## Selection

```json
{
  "adjusted_trade_count": 7,
  "by_ticker_count": {
    "CRDO": 3,
    "LLY": 1,
    "TSLA": 3
  },
  "by_ticker_incremental_pnl": {
    "CRDO": 5533.6,
    "LLY": -1121.8,
    "TSLA": 9082.25
  },
  "by_window_count": {
    "mid_weak": 5,
    "old_thin": 2
  },
  "by_window_incremental_pnl": {
    "mid_weak": 9784.71,
    "old_thin": 3709.34
  },
  "max_single_positive_incremental_pnl": 9082.25,
  "max_single_positive_pnl_share": 0.6214,
  "pnl_hhi_concentration": 0.5295,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "CRDO": 5533.6,
    "TSLA": 9082.25
  },
  "positive_incremental_pnl": 14615.85,
  "sample_rows": [
    {
      "adjusted_pnl": 5894.23,
      "baseline_pnl": 2947.11,
      "entry_date": "2025-04-28",
      "event_family": "periodic_report",
      "event_notional_rule": "periodic_report_10q_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 4.0,
      "exit_date": "2025-05-12",
      "form_base": "10-Q",
      "incremental_pnl": 2947.11,
      "language_bucket": null,
      "notional": 60000.0,
      "repeat_prior_age_days": 0,
      "repeat_prior_bucket": "open_positions",
      "repeat_prior_entry_date": "2025-04-25",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": 0.007225,
      "t1_excess_return_vs_spy": 0.090806,
      "t1_return": 0.098031,
      "text_event_type": null,
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 1713.95,
      "baseline_pnl": 856.98,
      "entry_date": "2025-07-07",
      "event_family": "periodic_report",
      "event_notional_rule": "periodic_report_default_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 2.5,
      "exit_date": "2025-07-21",
      "form_base": "10-K",
      "incremental_pnl": 856.98,
      "language_bucket": null,
      "notional": 37500.0,
      "repeat_prior_age_days": 28,
      "repeat_prior_bucket": "closed_positions",
      "repeat_prior_entry_date": "2025-06-05",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": 0.007881,
      "t1_excess_return_vs_spy": 0.039562,
      "t1_return": 0.047443,
      "text_event_type": null,
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 2608.0,
      "baseline_pnl": 1304.0,
      "entry_date": "2025-07-29",
      "event_family": "periodic_report",
      "event_notional_rule": "periodic_report_10q_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 4.0,
      "exit_date": "2025-08-12",
      "form_base": "10-Q",
      "incremental_pnl": 1304.0,
      "language_bucket": null,
      "notional": 60000.0,
      "repeat_prior_age_days": 0,
      "repeat_prior_bucket": "open_positions",
      "repeat_prior_entry_date": "2025-07-28",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": -0.000251,
      "t1_excess_return_vs_spy": 0.030404,
      "t1_return": 0.030152,
      "text_event_type": null,
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 4420.37,
      "baseline_pnl": 2210.19,
      "entry_date": "2025-09-08",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 2.2,
      "exit_date": "2025-09-22",
      "form_base": "8-K",
      "incremental_pnl": 2210.19,
      "language_bucket": "negative_language",
      "notional": 33000.0,
      "repeat_prior_age_days": 60,
      "repeat_prior_bucket": "closed_positions",
      "repeat_prior_entry_date": "2025-07-07",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": -0.002896,
      "t1_excess_return_vs_spy": 0.053792,
      "t1_return": 0.050896,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 4932.86,
      "baseline_pnl": 2466.43,
      "entry_date": "2025-09-09",
      "event_family": "periodic_report",
      "event_notional_rule": "periodic_report_10q_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 4.0,
      "exit_date": "2025-09-23",
      "form_base": "10-Q",
      "incremental_pnl": 2466.43,
      "language_bucket": null,
      "notional": 60000.0,
      "repeat_prior_age_days": 0,
      "repeat_prior_bucket": "open_positions",
      "repeat_prior_entry_date": "2025-09-08",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": 0.002457,
      "t1_excess_return_vs_spy": 0.045193,
      "t1_return": 0.047649,
      "text_event_type": null,
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 9662.28,
      "baseline_pnl": 4831.14,
      "entry_date": "2024-10-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 2.2,
      "exit_date": "2024-11-11",
      "form_base": "8-K",
      "incremental_pnl": 4831.14,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 33000.0,
      "repeat_prior_age_days": 18,
      "repeat_prior_bucket": "closed_positions",
      "repeat_prior_entry_date": "2024-10-07",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": -0.000345,
      "t1_excess_return_vs_spy": 0.033784,
      "t1_return": 0.033438,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -2243.6,
      "baseline_pnl": -1121.8,
      "entry_date": "2025-02-24",
      "event_family": "periodic_report",
      "event_notional_rule": "periodic_report_default_scalar+same_ticker_repeat_60d_scalar",
      "event_notional_scalar": 2.5,
      "exit_date": "2025-03-10",
      "form_base": "10-K",
      "incremental_pnl": -1121.8,
      "language_bucket": null,
      "notional": 37500.0,
      "repeat_prior_age_days": 35,
      "repeat_prior_bucket": "closed_positions",
      "repeat_prior_entry_date": "2025-01-17",
      "repeat_state": "repeat_within_60d",
      "spy_t1_return": -0.017104,
      "t1_excess_return_vs_spy": 0.017746,
      "t1_return": 0.000641,
      "text_event_type": null,
      "ticker": "LLY",
      "window": "old_thin"
    }
  ],
  "windows_present": 2
}
```

No JavaScript was used.
