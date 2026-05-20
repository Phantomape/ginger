# exp-20260520-011 SEC Neutral Earnings Moderate-Reaction Notional

Decision: `rejected_sec_neutral_earnings_moderate_reaction_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered earnings_release_text rows with neutral_or_mixed_language and moderate T+1 excess reaction may represent confirmed but not overextended post-earnings drift. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `moderate_reaction_scalar_0_00`
- target_scalar: `0.0`
- EV delta: `0.20854`
- PnL delta: `$-2047.17`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.3071 | $+2,138.20 | -0.0006 |
| mid_weak | -0.0652 | $-1,008.57 | +0.0000 |
| old_thin | -0.0334 | $-3,176.80 | +0.0018 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.20854,
    "expected_value_score_sum_delta_pct": 0.017578,
    "max_drawdown_pct_max_delta": 0.001803,
    "max_drawdown_pct_max_delta_pct": 0.015414,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": -1705.52,
    "sleeve_total_pnl_sum_delta_pct": -0.019528,
    "total_pnl_sum_delta": -2047.17,
    "total_pnl_sum_delta_pct": -0.006314,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.307136,
      "max_drawdown_pct": -0.000592,
      "sharpe_daily": 0.159906,
      "total_pnl": 2138.2
    },
    "mid_weak": {
      "expected_value_score": -0.065199,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": -0.024686,
      "total_pnl": -1008.57
    },
    "old_thin": {
      "expected_value_score": -0.033397,
      "max_drawdown_pct": 0.001803,
      "sharpe_daily": 0.044095,
      "total_pnl": -3176.8
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": false,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 9,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.001803,
    "max_single_positive_pnl_share": 0.5874,
    "pnl_hhi_concentration": 0.4004,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2
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
  "adjusted_trade_count": 9,
  "by_ticker_count": {
    "AAPL": 1,
    "INTC": 1,
    "MA": 1,
    "TSLA": 4,
    "UNH": 1,
    "V": 1
  },
  "by_ticker_incremental_pnl": {
    "AAPL": 339.86,
    "INTC": 770.43,
    "MA": 115.04,
    "TSLA": -3308.82,
    "UNH": -516.33,
    "V": 552.66
  },
  "by_window_count": {
    "late_strong": 4,
    "mid_weak": 1,
    "old_thin": 4
  },
  "by_window_incremental_pnl": {
    "late_strong": 2138.2,
    "mid_weak": -1008.57,
    "old_thin": -3176.79
  },
  "max_single_positive_incremental_pnl": 2530.89,
  "max_single_positive_pnl_share": 0.5874,
  "pnl_hhi_concentration": 0.4004,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "AAPL": 339.86,
    "INTC": 770.43,
    "MA": 115.04,
    "TSLA": 2530.89,
    "V": 552.66
  },
  "positive_incremental_pnl": 4308.88,
  "sample_rows": [
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -770.43,
      "entry_date": "2025-10-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-11-11",
      "form_base": "8-K",
      "incremental_pnl": 770.43,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.011798,
      "t1_excess_return_vs_spy": 0.021118,
      "t1_return": 0.032915,
      "text_event_type": "earnings_release_text",
      "ticker": "INTC",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -552.66,
      "entry_date": "2025-10-31",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-11-14",
      "form_base": "8-K",
      "incremental_pnl": 552.66,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": -0.010998,
      "t1_excess_return_vs_spy": 0.021986,
      "t1_return": 0.010988,
      "text_event_type": "earnings_release_text",
      "ticker": "V",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -475.25,
      "entry_date": "2026-02-02",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2026-02-17",
      "form_base": "8-K",
      "incremental_pnl": 475.25,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": -0.002983,
      "t1_excess_return_vs_spy": 0.036231,
      "t1_return": 0.033249,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -339.86,
      "entry_date": "2026-02-03",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2026-02-18",
      "form_base": "8-K",
      "incremental_pnl": 339.86,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.004971,
      "t1_excess_return_vs_spy": 0.03561,
      "t1_return": 0.040581,
      "text_event_type": "earnings_release_text",
      "ticker": "AAPL",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 0.0,
      "baseline_pnl": 1008.57,
      "entry_date": "2025-07-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-08-11",
      "form_base": "8-K",
      "incremental_pnl": -1008.57,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.004224,
      "t1_excess_return_vs_spy": 0.03102,
      "t1_return": 0.035244,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -2055.64,
      "entry_date": "2024-10-07",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2024-10-21",
      "form_base": "8-K",
      "incremental_pnl": 2055.64,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.009087,
      "t1_excess_return_vs_spy": 0.030055,
      "t1_return": 0.039142,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 0.0,
      "baseline_pnl": 4831.14,
      "entry_date": "2024-10-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2024-11-11",
      "form_base": "8-K",
      "incremental_pnl": -4831.14,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": -0.000345,
      "t1_excess_return_vs_spy": 0.033784,
      "t1_return": 0.033438,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 0.0,
      "baseline_pnl": 516.33,
      "entry_date": "2025-01-22",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-02-05",
      "form_base": "8-K",
      "incremental_pnl": -516.33,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.009153,
      "t1_excess_return_vs_spy": 0.020723,
      "t1_return": 0.029877,
      "text_event_type": "earnings_release_text",
      "ticker": "UNH",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -115.04,
      "entry_date": "2025-02-04",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_earnings_moderate_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-02-19",
      "form_base": "8-K",
      "incremental_pnl": 115.04,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": -0.00673,
      "t1_excess_return_vs_spy": 0.022069,
      "t1_return": 0.01534,
      "text_event_type": "earnings_release_text",
      "ticker": "MA",
      "window": "old_thin"
    }
  ],
  "windows_present": 3
}
```

No JavaScript was used.
