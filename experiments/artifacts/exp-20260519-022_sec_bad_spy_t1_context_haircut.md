# exp-20260519-022 SEC Bad-SPY T+1 Context Haircut

Decision: `rejected_sec_bad_spy_t1_context_haircut`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered rows following a SPY T+1 return below -0.5% may be broad-market fragility rather than firm-specific post-filing drift. A bounded paper-notional haircut could improve risk allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `sec_bad_spy_t1_context_scalar_0_00`
- target_scalar: `0.0`
- EV delta: `0.108893`
- PnL delta: `$1956.23`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0620 | $+552.66 | -0.0002 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 |
| old_thin | +0.0469 | $+1,403.57 | -0.0003 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.108893,
    "expected_value_score_sum_delta_pct": 0.009179,
    "max_drawdown_pct_max_delta": -0.000341,
    "max_drawdown_pct_max_delta_pct": -0.002915,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 1956.23,
    "sleeve_total_pnl_sum_delta_pct": 0.022398,
    "total_pnl_sum_delta": 1956.23,
    "total_pnl_sum_delta_pct": 0.006033,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.062036,
      "max_drawdown_pct": -0.000249,
      "sharpe_daily": 0.028475,
      "total_pnl": 552.66
    },
    "mid_weak": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.046857,
      "max_drawdown_pct": -0.000341,
      "sharpe_daily": 0.019376,
      "total_pnl": 1403.57
    }
  },
  "checks": {
    "adjusted_trade_sample": false,
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
    "adjusted_trade_count": 5,
    "adjusted_windows": [
      "late_strong",
      "old_thin"
    ],
    "max_drawdown_worse": 0.0,
    "max_single_positive_pnl_share": 0.6173,
    "pnl_hhi_concentration": 0.456,
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
  "adjusted_trade_count": 5,
  "by_ticker_count": {
    "JPM": 1,
    "MA": 1,
    "MCD": 1,
    "TSLA": 1,
    "V": 1
  },
  "by_ticker_incremental_pnl": {
    "JPM": -175.66,
    "MA": 115.04,
    "MCD": 148.25,
    "TSLA": 1315.95,
    "V": 552.66
  },
  "by_window_count": {
    "late_strong": 1,
    "old_thin": 4
  },
  "by_window_incremental_pnl": {
    "late_strong": 552.66,
    "old_thin": 1403.58
  },
  "max_single_positive_incremental_pnl": 1315.95,
  "max_single_positive_pnl_share": 0.6173,
  "pnl_hhi_concentration": 0.456,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "MA": 115.04,
    "MCD": 148.25,
    "TSLA": 1315.95,
    "V": 552.66
  },
  "positive_incremental_pnl": 2131.9,
  "sample_rows": [
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -552.66,
      "entry_date": "2025-10-31",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+sec_bad_spy_t1_context_scalar",
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
      "adjusted_pnl": 0.0,
      "baseline_pnl": 175.66,
      "entry_date": "2024-10-16",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+neutral_underreaction_scalar+sec_bad_spy_t1_context_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2024-10-30",
      "form_base": "8-K",
      "incremental_pnl": -175.66,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": -0.00777,
      "t1_excess_return_vs_spy": 0.011878,
      "t1_return": 0.004109,
      "text_event_type": "earnings_release_text",
      "ticker": "JPM",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -148.25,
      "entry_date": "2024-11-01",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+sec_bad_spy_t1_context_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2024-11-15",
      "form_base": "8-K",
      "incremental_pnl": 148.25,
      "language_bucket": "negative_language",
      "notional": 0.0,
      "spy_t1_return": -0.019603,
      "t1_excess_return_vs_spy": 0.021627,
      "t1_return": 0.002024,
      "text_event_type": "earnings_release_text",
      "ticker": "MCD",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -1315.95,
      "entry_date": "2025-02-03",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+sec_bad_spy_t1_context_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-02-18",
      "form_base": "8-K",
      "incremental_pnl": 1315.95,
      "language_bucket": "positive_language",
      "notional": 0.0,
      "spy_t1_return": -0.005322,
      "t1_excess_return_vs_spy": 0.016114,
      "t1_return": 0.010792,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -115.04,
      "entry_date": "2025-02-04",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+sec_bad_spy_t1_context_scalar",
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
  "windows_present": 2
}
```

No JavaScript was used.
