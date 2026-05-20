# exp-20260520-010 SEC Neutral Earnings Underreaction Notional

Decision: `rejected_sec_neutral_earnings_underreaction_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered earnings_release_text rows with neutral_or_mixed_language and muted T+1 excess reaction may be underreaction candidates. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `neutral_earnings_underreaction_scalar_1_50`
- target_scalar: `1.5`
- EV delta: `0.940207`
- PnL delta: `$25737.31`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.1411 | $+2,305.57 | +0.0000 |
| mid_weak | +0.4320 | $+7,083.94 | -0.0026 |
| old_thin | +0.3671 | $+16,347.80 | +0.0057 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.940207,
    "expected_value_score_sum_delta_pct": 0.079252,
    "max_drawdown_pct_max_delta": 0.005657,
    "max_drawdown_pct_max_delta_pct": 0.048362,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 25737.31,
    "sleeve_total_pnl_sum_delta_pct": 0.294684,
    "total_pnl_sum_delta": 25737.31,
    "total_pnl_sum_delta_pct": 0.079379,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.141094,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.027776,
      "total_pnl": 2305.57
    },
    "mid_weak": {
      "expected_value_score": 0.432003,
      "max_drawdown_pct": -0.002634,
      "sharpe_daily": 0.13966,
      "total_pnl": 7083.94
    },
    "old_thin": {
      "expected_value_score": 0.36711,
      "max_drawdown_pct": 0.005657,
      "sharpe_daily": 0.012999,
      "total_pnl": 16347.8
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": false,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 6,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.005657,
    "max_single_positive_pnl_share": 0.6762,
    "pnl_hhi_concentration": 0.4927,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 3,
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
  "adjusted_trade_count": 6,
  "by_ticker_count": {
    "BKNG": 2,
    "COIN": 1,
    "JPM": 1,
    "LLY": 1,
    "TSLA": 1
  },
  "by_ticker_incremental_pnl": {
    "BKNG": -1274.7,
    "COIN": 19884.89,
    "JPM": 87.83,
    "LLY": 3711.86,
    "TSLA": 3372.08
  },
  "by_window_count": {
    "late_strong": 1,
    "mid_weak": 2,
    "old_thin": 3
  },
  "by_window_incremental_pnl": {
    "late_strong": 2350.21,
    "mid_weak": 7083.94,
    "old_thin": 16347.81
  },
  "max_single_positive_incremental_pnl": 19884.89,
  "max_single_positive_pnl_share": 0.6762,
  "pnl_hhi_concentration": 0.4927,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "BKNG": 2350.21,
    "COIN": 19884.89,
    "JPM": 87.83,
    "LLY": 3711.86,
    "TSLA": 3372.08
  },
  "positive_incremental_pnl": 29406.87,
  "sample_rows": [
    {
      "adjusted_pnl": 7050.64,
      "baseline_pnl": 4700.43,
      "entry_date": "2026-02-23",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_underreaction_scalar",
      "event_notional_scalar": 4.95,
      "exit_date": "2026-03-09",
      "form_base": "8-K",
      "incremental_pnl": 2350.21,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 74250.0,
      "spy_t1_return": 0.007232,
      "t1_excess_return_vs_spy": 0.010071,
      "t1_return": 0.017303,
      "text_event_type": "earnings_release_text",
      "ticker": "BKNG",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 10116.23,
      "baseline_pnl": 6744.15,
      "entry_date": "2025-04-25",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_underreaction_scalar",
      "event_notional_scalar": 4.95,
      "exit_date": "2025-05-09",
      "form_base": "8-K",
      "incremental_pnl": 3372.08,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 74250.0,
      "spy_t1_return": 0.021049,
      "t1_excess_return_vs_spy": 0.013927,
      "t1_return": 0.034976,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 11135.57,
      "baseline_pnl": 7423.72,
      "entry_date": "2025-08-12",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_underreaction_scalar",
      "event_notional_scalar": 4.95,
      "exit_date": "2025-08-26",
      "form_base": "8-K",
      "incremental_pnl": 3711.86,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 74250.0,
      "spy_t1_return": -0.001978,
      "t1_excess_return_vs_spy": 0.017273,
      "t1_return": 0.015296,
      "text_event_type": "earnings_release_text",
      "ticker": "LLY",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 263.49,
      "baseline_pnl": 175.66,
      "entry_date": "2024-10-16",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_earnings_underreaction_scalar",
      "event_notional_scalar": 3.0,
      "exit_date": "2024-10-30",
      "form_base": "8-K",
      "incremental_pnl": 87.83,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 45000.0,
      "spy_t1_return": -0.00777,
      "t1_excess_return_vs_spy": 0.011878,
      "t1_return": 0.004109,
      "text_event_type": "earnings_release_text",
      "ticker": "JPM",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 59654.67,
      "baseline_pnl": 39769.78,
      "entry_date": "2024-11-04",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_underreaction_scalar",
      "event_notional_scalar": 4.95,
      "exit_date": "2024-11-18",
      "form_base": "8-K",
      "incremental_pnl": 19884.89,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 74250.0,
      "spy_t1_return": 0.00422,
      "t1_excess_return_vs_spy": 0.016031,
      "t1_return": 0.020251,
      "text_event_type": "earnings_release_text",
      "ticker": "COIN",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -10874.74,
      "baseline_pnl": -7249.83,
      "entry_date": "2025-02-25",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_underreaction_scalar",
      "event_notional_scalar": 4.95,
      "exit_date": "2025-03-11",
      "form_base": "8-K",
      "incremental_pnl": -3624.91,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 74250.0,
      "spy_t1_return": -0.00455,
      "t1_excess_return_vs_spy": 0.01626,
      "t1_return": 0.01171,
      "text_event_type": "earnings_release_text",
      "ticker": "BKNG",
      "window": "old_thin"
    }
  ],
  "windows_present": 3
}
```

No JavaScript was used.
