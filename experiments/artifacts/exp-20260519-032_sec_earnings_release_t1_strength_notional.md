# exp-20260519-032 SEC Earnings-Release T+1 Strength Notional

Decision: `rejected_sec_earnings_release_t1_strength_notional`.

## Hypothesis

Within the accepted SEC earnings-release SPY-context paper branch, rows with t1_excess_return_vs_spy >= 0.03 may have stronger post-event continuation; a bounded paper-notional scalar can improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `t1_strength_scalar_1_25`
- target_scalar: `1.25`
- EV delta: `0.098778`
- PnL delta: `$2277.38`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0492 | $+904.33 | -0.0004 |
| mid_weak | +0.0652 | $+1,176.50 | -0.0003 |
| old_thin | -0.0156 | $+196.55 | +0.0010 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.098778,
    "expected_value_score_sum_delta_pct": 0.008938,
    "max_drawdown_pct_max_delta": 0.000961,
    "max_drawdown_pct_max_delta_pct": 0.008216,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 2254.5,
    "sleeve_total_pnl_sum_delta_pct": 0.025813,
    "total_pnl_sum_delta": 2277.38,
    "total_pnl_sum_delta_pct": 0.007322,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.049214,
      "max_drawdown_pct": -0.000411,
      "sharpe_daily": 0.006305,
      "total_pnl": 904.33
    },
    "mid_weak": {
      "expected_value_score": 0.065196,
      "max_drawdown_pct": -0.000347,
      "sharpe_daily": 0.024856,
      "total_pnl": 1176.5
    },
    "old_thin": {
      "expected_value_score": -0.015632,
      "max_drawdown_pct": 0.000961,
      "sharpe_daily": -0.023765,
      "total_pnl": 196.55
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 15,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.000961,
    "max_single_positive_pnl_share": 0.3955,
    "pnl_hhi_concentration": 0.2975,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 2,
    "windows_ev_regressed": 1
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
  "adjusted_trade_count": 15,
  "by_ticker_count": {
    "AAPL": 1,
    "AVGO": 1,
    "CAT": 1,
    "CRDO": 3,
    "DE": 2,
    "MU": 1,
    "TRIP": 1,
    "TSLA": 5
  },
  "by_ticker_incremental_pnl": {
    "AAPL": -84.96,
    "AVGO": -152.4,
    "CAT": 327.81,
    "CRDO": 897.19,
    "DE": -344.92,
    "MU": 916.34,
    "TRIP": -46.35,
    "TSLA": 764.68
  },
  "by_window_count": {
    "late_strong": 6,
    "mid_weak": 4,
    "old_thin": 5
  },
  "by_window_incremental_pnl": {
    "late_strong": 904.34,
    "mid_weak": 1176.5,
    "old_thin": 196.55
  },
  "max_single_positive_incremental_pnl": 1459.92,
  "max_single_positive_pnl_share": 0.3955,
  "pnl_hhi_concentration": 0.2975,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "CAT": 327.81,
    "CRDO": 986.88,
    "MU": 916.34,
    "TSLA": 1459.92
  },
  "positive_incremental_pnl": 3690.95,
  "sample_rows": [
    {
      "adjusted_pnl": 4581.71,
      "baseline_pnl": 3665.37,
      "entry_date": "2025-12-22",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2026-01-07",
      "form_base": "8-K",
      "incremental_pnl": 916.34,
      "language_bucket": "positive_language",
      "notional": 20625.0,
      "spy_t1_return": 0.009063,
      "t1_excess_return_vs_spy": 0.060822,
      "t1_return": 0.069885,
      "text_event_type": "earnings_release_text",
      "ticker": "MU",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -594.07,
      "baseline_pnl": -475.25,
      "entry_date": "2026-02-02",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2026-02-17",
      "form_base": "8-K",
      "incremental_pnl": -118.81,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": -0.002983,
      "t1_excess_return_vs_spy": 0.036231,
      "t1_return": 0.033249,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 1639.04,
      "baseline_pnl": 1311.23,
      "entry_date": "2026-02-03",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2026-02-18",
      "form_base": "8-K",
      "incremental_pnl": 327.81,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.004971,
      "t1_excess_return_vs_spy": 0.046066,
      "t1_return": 0.051037,
      "text_event_type": "earnings_release_text",
      "ticker": "CAT",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -424.82,
      "baseline_pnl": -339.86,
      "entry_date": "2026-02-03",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2026-02-18",
      "form_base": "8-K",
      "incremental_pnl": -84.96,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.004971,
      "t1_excess_return_vs_spy": 0.03561,
      "t1_return": 0.040581,
      "text_event_type": "earnings_release_text",
      "ticker": "AAPL",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -231.76,
      "baseline_pnl": -185.41,
      "entry_date": "2026-02-18",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2026-03-04",
      "form_base": "8-K",
      "incremental_pnl": -46.35,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.001613,
      "t1_excess_return_vs_spy": 0.095161,
      "t1_return": 0.096774,
      "text_event_type": "earnings_release_text",
      "ticker": "TRIP",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -448.46,
      "baseline_pnl": -358.77,
      "entry_date": "2026-03-05",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2026-03-19",
      "form_base": "8-K",
      "incremental_pnl": -89.69,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.007055,
      "t1_excess_return_vs_spy": 0.046799,
      "t1_return": 0.053854,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 2171.64,
      "baseline_pnl": 1737.31,
      "entry_date": "2025-06-05",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-06-20",
      "form_base": "8-K",
      "incremental_pnl": 434.33,
      "language_bucket": "negative_language",
      "notional": 20625.0,
      "spy_t1_return": -0.000268,
      "t1_excess_return_vs_spy": 0.063394,
      "t1_return": 0.063126,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 1260.71,
      "baseline_pnl": 1008.57,
      "entry_date": "2025-07-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-08-11",
      "form_base": "8-K",
      "incremental_pnl": 252.14,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.004224,
      "t1_excess_return_vs_spy": 0.03102,
      "t1_return": 0.035244,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 2762.73,
      "baseline_pnl": 2210.19,
      "entry_date": "2025-09-08",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-09-22",
      "form_base": "8-K",
      "incremental_pnl": 552.55,
      "language_bucket": "negative_language",
      "notional": 20625.0,
      "spy_t1_return": -0.002896,
      "t1_excess_return_vs_spy": 0.053792,
      "t1_return": 0.050896,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -312.6,
      "baseline_pnl": -250.08,
      "entry_date": "2025-10-07",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-10-21",
      "form_base": "8-K",
      "incremental_pnl": -62.52,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.003586,
      "t1_excess_return_vs_spy": 0.0509,
      "t1_return": 0.054487,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -2569.55,
      "baseline_pnl": -2055.64,
      "entry_date": "2024-10-07",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2024-10-21",
      "form_base": "8-K",
      "incremental_pnl": -513.91,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.009087,
      "t1_excess_return_vs_spy": 0.030055,
      "t1_return": 0.039142,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 6038.92,
      "baseline_pnl": 4831.14,
      "entry_date": "2024-10-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2024-11-11",
      "form_base": "8-K",
      "incremental_pnl": 1207.78,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": -0.000345,
      "t1_excess_return_vs_spy": 0.033784,
      "t1_return": 0.033438,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -461.07,
      "baseline_pnl": -368.86,
      "entry_date": "2024-11-26",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2024-12-11",
      "form_base": "8-K",
      "incremental_pnl": -92.21,
      "language_bucket": "negative_language",
      "notional": 20625.0,
      "spy_t1_return": 0.003392,
      "t1_excess_return_vs_spy": 0.03252,
      "t1_return": 0.035912,
      "text_event_type": "earnings_release_text",
      "ticker": "DE",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -761.98,
      "baseline_pnl": -609.58,
      "entry_date": "2024-12-17",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-01-02",
      "form_base": "8-K",
      "incremental_pnl": -152.4,
      "language_bucket": "positive_language",
      "notional": 20625.0,
      "spy_t1_return": 0.00427,
      "t1_excess_return_vs_spy": 0.10783,
      "t1_return": 0.1121,
      "text_event_type": "earnings_release_text",
      "ticker": "AVGO",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -1263.56,
      "baseline_pnl": -1010.85,
      "entry_date": "2025-02-19",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+earnings_release_text_t1_strength_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-03-05",
      "form_base": "8-K",
      "incremental_pnl": -252.71,
      "language_bucket": "negative_language",
      "notional": 20625.0,
      "spy_t1_return": 0.002936,
      "t1_excess_return_vs_spy": 0.041502,
      "t1_return": 0.044438,
      "text_event_type": "earnings_release_text",
      "ticker": "DE",
      "window": "old_thin"
    }
  ],
  "windows_present": 3
}
```

No JavaScript was used.
