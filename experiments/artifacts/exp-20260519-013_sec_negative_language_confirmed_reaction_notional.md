# exp-20260519-013 SEC Negative-Language Confirmed Reaction Notional

Decision: `rejected_sec_negative_language_confirmed_reaction_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered negative_language rows with strong positive T+1 excess reaction may represent market-confirmed bad-news absorption. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `confirmed_reaction_scalar_2_00`
- target_scalar: `2.0`
- EV delta: `0.18216`
- PnL delta: `$2419.54`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 |
| mid_weak | +0.2344 | $+3,947.50 | -0.0014 |
| old_thin | -0.0522 | $-1,527.96 | +0.0052 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.18216,
    "expected_value_score_sum_delta_pct": 0.015355,
    "max_drawdown_pct_max_delta": 0.005168,
    "max_drawdown_pct_max_delta_pct": 0.044182,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 2328.04,
    "sleeve_total_pnl_sum_delta_pct": 0.026655,
    "total_pnl_sum_delta": 2419.54,
    "total_pnl_sum_delta_pct": 0.007462,
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
      "expected_value_score": 0.234402,
      "max_drawdown_pct": -0.001375,
      "sharpe_daily": 0.074455,
      "total_pnl": 3947.5
    },
    "old_thin": {
      "expected_value_score": -0.052242,
      "max_drawdown_pct": 0.005168,
      "sharpe_daily": -0.023354,
      "total_pnl": -1527.96
    }
  },
  "checks": {
    "adjusted_trade_sample": false,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": false,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 5,
    "adjusted_windows": [
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.005168,
    "max_single_positive_pnl_share": 1.0,
    "pnl_hhi_concentration": 1.0,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 1,
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
  "adjusted_trade_count": 5,
  "by_ticker_count": {
    "CRDO": 2,
    "DE": 2,
    "MCD": 1
  },
  "by_ticker_incremental_pnl": {
    "CRDO": 3947.5,
    "DE": -1379.71,
    "MCD": -148.25
  },
  "by_window_count": {
    "mid_weak": 2,
    "old_thin": 3
  },
  "by_window_incremental_pnl": {
    "mid_weak": 3947.5,
    "old_thin": -1527.96
  },
  "max_single_positive_incremental_pnl": 3947.5,
  "max_single_positive_pnl_share": 1.0,
  "pnl_hhi_concentration": 1.0,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "CRDO": 3947.5
  },
  "positive_incremental_pnl": 3947.5,
  "sample_rows": [
    {
      "adjusted_pnl": 3474.62,
      "baseline_pnl": 1737.31,
      "entry_date": "2025-06-05",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+negative_language_confirmed_reaction_scalar",
      "event_notional_scalar": 2.2,
      "exit_date": "2025-06-20",
      "form_base": "8-K",
      "incremental_pnl": 1737.31,
      "language_bucket": "negative_language",
      "notional": 33000.0,
      "spy_t1_return": -0.000268,
      "t1_excess_return_vs_spy": 0.063394,
      "t1_return": 0.063126,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 4420.37,
      "baseline_pnl": 2210.19,
      "entry_date": "2025-09-08",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+negative_language_confirmed_reaction_scalar",
      "event_notional_scalar": 2.2,
      "exit_date": "2025-09-22",
      "form_base": "8-K",
      "incremental_pnl": 2210.19,
      "language_bucket": "negative_language",
      "notional": 33000.0,
      "spy_t1_return": -0.002896,
      "t1_excess_return_vs_spy": 0.053792,
      "t1_return": 0.050896,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -296.51,
      "baseline_pnl": -148.25,
      "entry_date": "2024-11-01",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+negative_language_confirmed_reaction_scalar",
      "event_notional_scalar": 2.0,
      "exit_date": "2024-11-15",
      "form_base": "8-K",
      "incremental_pnl": -148.25,
      "language_bucket": "negative_language",
      "notional": 30000.0,
      "spy_t1_return": -0.019603,
      "t1_excess_return_vs_spy": 0.021627,
      "t1_return": 0.002024,
      "text_event_type": "earnings_release_text",
      "ticker": "MCD",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -737.72,
      "baseline_pnl": -368.86,
      "entry_date": "2024-11-26",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+negative_language_confirmed_reaction_scalar",
      "event_notional_scalar": 2.2,
      "exit_date": "2024-12-11",
      "form_base": "8-K",
      "incremental_pnl": -368.86,
      "language_bucket": "negative_language",
      "notional": 33000.0,
      "spy_t1_return": 0.003392,
      "t1_excess_return_vs_spy": 0.03252,
      "t1_return": 0.035912,
      "text_event_type": "earnings_release_text",
      "ticker": "DE",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -2021.7,
      "baseline_pnl": -1010.85,
      "entry_date": "2025-02-19",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+negative_language_confirmed_reaction_scalar",
      "event_notional_scalar": 2.2,
      "exit_date": "2025-03-05",
      "form_base": "8-K",
      "incremental_pnl": -1010.85,
      "language_bucket": "negative_language",
      "notional": 33000.0,
      "spy_t1_return": 0.002936,
      "t1_excess_return_vs_spy": 0.041502,
      "t1_return": 0.044438,
      "text_event_type": "earnings_release_text",
      "ticker": "DE",
      "window": "old_thin"
    }
  ],
  "windows_present": 2
}
```

No JavaScript was used.
