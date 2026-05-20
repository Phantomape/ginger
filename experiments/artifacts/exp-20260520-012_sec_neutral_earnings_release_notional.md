# exp-20260520-012 SEC Neutral Earnings-Release Notional

Decision: `rejected_sec_neutral_earnings_release_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered earnings_release_text rows with neutral_or_mixed_language may represent factual underreaction without promotional excess. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `neutral_earnings_release_scalar_1_25`
- target_scalar: `1.25`
- EV delta: `0.413449`
- PnL delta: `$13509.69`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | -0.0096 | $+810.00 | +0.0001 |
| mid_weak | +0.2304 | $+3,731.59 | -0.0013 |
| old_thin | +0.1927 | $+8,968.10 | +0.0025 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.413449,
    "expected_value_score_sum_delta_pct": 0.034851,
    "max_drawdown_pct_max_delta": 0.002525,
    "max_drawdown_pct_max_delta_pct": 0.021587,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 13424.28,
    "sleeve_total_pnl_sum_delta_pct": 0.153704,
    "total_pnl_sum_delta": 13509.69,
    "total_pnl_sum_delta_pct": 0.041667,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": -0.009579,
      "max_drawdown_pct": 0.00015,
      "sharpe_daily": -0.035588,
      "total_pnl": 810.0
    },
    "mid_weak": {
      "expected_value_score": 0.230368,
      "max_drawdown_pct": -0.001335,
      "sharpe_daily": 0.078144,
      "total_pnl": 3731.59
    },
    "old_thin": {
      "expected_value_score": 0.19266,
      "max_drawdown_pct": 0.002525,
      "sharpe_daily": -0.00174,
      "total_pnl": 8968.1
    }
  },
  "checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 19,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.002525,
    "max_single_positive_pnl_share": 0.5982,
    "pnl_hhi_concentration": 0.4116,
    "pnl_top_5_contribution_pct": 0.9896,
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
  "adjusted_trade_count": 19,
  "by_ticker_count": {
    "AAPL": 1,
    "BKNG": 2,
    "CAT": 1,
    "COIN": 1,
    "CRDO": 1,
    "INTC": 1,
    "JPM": 1,
    "LLY": 1,
    "MA": 1,
    "TRIP": 1,
    "TSLA": 6,
    "UNH": 1,
    "V": 1
  },
  "by_ticker_incremental_pnl": {
    "AAPL": -84.96,
    "BKNG": -637.35,
    "CAT": 327.81,
    "COIN": 9942.45,
    "CRDO": -89.69,
    "INTC": -192.61,
    "JPM": 43.92,
    "LLY": 1855.93,
    "MA": -28.76,
    "TRIP": -46.35,
    "TSLA": 2450.72,
    "UNH": 129.08,
    "V": -138.17
  },
  "by_window_count": {
    "late_strong": 8,
    "mid_weak": 4,
    "old_thin": 7
  },
  "by_window_incremental_pnl": {
    "late_strong": 832.33,
    "mid_weak": 3731.59,
    "old_thin": 8968.1
  },
  "max_single_positive_incremental_pnl": 9942.45,
  "max_single_positive_pnl_share": 0.5982,
  "pnl_hhi_concentration": 0.4116,
  "pnl_top_5_contribution_pct": 0.9896,
  "positive_by_ticker_incremental_pnl": {
    "BKNG": 1175.11,
    "CAT": 327.81,
    "COIN": 9942.45,
    "JPM": 43.92,
    "LLY": 1855.93,
    "TSLA": 3145.96,
    "UNH": 129.08
  },
  "positive_incremental_pnl": 16620.26,
  "sample_rows": [
    {
      "adjusted_pnl": -963.04,
      "baseline_pnl": -770.43,
      "entry_date": "2025-10-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-11-11",
      "form_base": "8-K",
      "incremental_pnl": -192.61,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.011798,
      "t1_excess_return_vs_spy": 0.021118,
      "t1_return": 0.032915,
      "text_event_type": "earnings_release_text",
      "ticker": "INTC",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -690.83,
      "baseline_pnl": -552.66,
      "entry_date": "2025-10-31",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_earnings_release_scalar",
      "event_notional_scalar": 1.25,
      "exit_date": "2025-11-14",
      "form_base": "8-K",
      "incremental_pnl": -138.17,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 18750.0,
      "spy_t1_return": -0.010998,
      "t1_excess_return_vs_spy": 0.021986,
      "t1_return": 0.010988,
      "text_event_type": "earnings_release_text",
      "ticker": "V",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -594.07,
      "baseline_pnl": -475.25,
      "entry_date": "2026-02-02",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "adjusted_pnl": 5875.53,
      "baseline_pnl": 4700.43,
      "entry_date": "2026-02-23",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 4.125,
      "exit_date": "2026-03-09",
      "form_base": "8-K",
      "incremental_pnl": 1175.11,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 61875.0,
      "spy_t1_return": 0.007232,
      "t1_excess_return_vs_spy": 0.010071,
      "t1_return": 0.017303,
      "text_event_type": "earnings_release_text",
      "ticker": "BKNG",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -448.46,
      "baseline_pnl": -358.77,
      "entry_date": "2026-03-05",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "adjusted_pnl": 8430.19,
      "baseline_pnl": 6744.15,
      "entry_date": "2025-04-25",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 4.125,
      "exit_date": "2025-05-09",
      "form_base": "8-K",
      "incremental_pnl": 1686.04,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 61875.0,
      "spy_t1_return": 0.021049,
      "t1_excess_return_vs_spy": 0.013927,
      "t1_return": 0.034976,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 1260.71,
      "baseline_pnl": 1008.57,
      "entry_date": "2025-07-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "adjusted_pnl": 9279.64,
      "baseline_pnl": 7423.72,
      "entry_date": "2025-08-12",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 4.125,
      "exit_date": "2025-08-26",
      "form_base": "8-K",
      "incremental_pnl": 1855.93,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 61875.0,
      "spy_t1_return": -0.001978,
      "t1_excess_return_vs_spy": 0.017273,
      "t1_return": 0.015296,
      "text_event_type": "earnings_release_text",
      "ticker": "LLY",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -312.6,
      "baseline_pnl": -250.08,
      "entry_date": "2025-10-07",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "adjusted_pnl": 219.58,
      "baseline_pnl": 175.66,
      "entry_date": "2024-10-16",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 2.5,
      "exit_date": "2024-10-30",
      "form_base": "8-K",
      "incremental_pnl": 43.92,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 37500.0,
      "spy_t1_return": -0.00777,
      "t1_excess_return_vs_spy": 0.011878,
      "t1_return": 0.004109,
      "text_event_type": "earnings_release_text",
      "ticker": "JPM",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 6038.92,
      "baseline_pnl": 4831.14,
      "entry_date": "2024-10-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
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
      "adjusted_pnl": 49712.23,
      "baseline_pnl": 39769.78,
      "entry_date": "2024-11-04",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 4.125,
      "exit_date": "2024-11-18",
      "form_base": "8-K",
      "incremental_pnl": 9942.45,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 61875.0,
      "spy_t1_return": 0.00422,
      "t1_excess_return_vs_spy": 0.016031,
      "t1_return": 0.020251,
      "text_event_type": "earnings_release_text",
      "ticker": "COIN",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 645.41,
      "baseline_pnl": 516.33,
      "entry_date": "2025-01-22",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 1.375,
      "exit_date": "2025-02-05",
      "form_base": "8-K",
      "incremental_pnl": 129.08,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 20625.0,
      "spy_t1_return": 0.009153,
      "t1_excess_return_vs_spy": 0.020723,
      "t1_return": 0.029877,
      "text_event_type": "earnings_release_text",
      "ticker": "UNH",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -143.79,
      "baseline_pnl": -115.04,
      "entry_date": "2025-02-04",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_earnings_release_scalar",
      "event_notional_scalar": 1.25,
      "exit_date": "2025-02-19",
      "form_base": "8-K",
      "incremental_pnl": -28.76,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 18750.0,
      "spy_t1_return": -0.00673,
      "t1_excess_return_vs_spy": 0.022069,
      "t1_return": 0.01534,
      "text_event_type": "earnings_release_text",
      "ticker": "MA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -9062.29,
      "baseline_pnl": -7249.83,
      "entry_date": "2025-02-25",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+neutral_underreaction_spy_t1_context_scalar+earnings_release_text_spy_t1_context_scalar+neutral_earnings_release_scalar",
      "event_notional_scalar": 4.125,
      "exit_date": "2025-03-11",
      "form_base": "8-K",
      "incremental_pnl": -1812.46,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 61875.0,
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
