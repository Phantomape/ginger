# exp-20260520-015 SEC Clean-Positive Earnings-Release Notional

Decision: `rejected_sec_clean_positive_earnings_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered earnings_release_text rows with positive_language and no negative phrase or guidance-cut hits may represent cleaner fact/tone alignment than the broad positive-language bucket. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, LLM authority, or live orders.

## Best Variant

- best_variant: `clean_positive_earnings_scalar_1_50`
- target_scalar: `1.5`
- EV delta: `0.217963`
- PnL delta: `$3024.43`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.1575 | $+1,832.69 | -0.0008 |
| mid_weak | +0.0305 | $+346.19 | -0.0003 |
| old_thin | +0.0300 | $+845.55 | -0.0005 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.217963,
    "expected_value_score_sum_delta_pct": 0.018373,
    "max_drawdown_pct_max_delta": -0.000474,
    "max_drawdown_pct_max_delta_pct": -0.004052,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 3024.43,
    "sleeve_total_pnl_sum_delta_pct": 0.034629,
    "total_pnl_sum_delta": 3024.43,
    "total_pnl_sum_delta_pct": 0.009328,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.157494,
      "max_drawdown_pct": -0.000817,
      "sharpe_daily": 0.056732,
      "total_pnl": 1832.69
    },
    "mid_weak": {
      "expected_value_score": 0.030474,
      "max_drawdown_pct": -0.000277,
      "sharpe_daily": 0.015613,
      "total_pnl": 346.19
    },
    "old_thin": {
      "expected_value_score": 0.029995,
      "max_drawdown_pct": -0.000474,
      "sharpe_daily": 0.013846,
      "total_pnl": 845.55
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
    "adjusted_trade_count": 3,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": -0.000277,
    "max_single_positive_pnl_share": 0.8855,
    "pnl_hhi_concentration": 0.7973,
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

## Coverage

```json
{
  "aggregate": {
    "non_target": 101,
    "target": 7
  },
  "by_window": {
    "late_strong": {
      "candidate_count": 39,
      "target_count": 2
    },
    "mid_weak": {
      "candidate_count": 29,
      "target_count": 3
    },
    "old_thin": {
      "candidate_count": 40,
      "target_count": 2
    }
  },
  "target_definition": {
    "guidance_cut_hits_lte": 0,
    "language_bucket": "positive_language",
    "negative_phrase_hits_lte": 0,
    "positive_phrase_plus_guidance_raise_hits_gte": 1,
    "sec_text_coverage_status": "covered",
    "text_event_type": "earnings_release_text"
  },
  "target_hit_profiles": {
    "0p_0n_1gr_0gc": 1,
    "10p_0n_8gr_0gc": 1,
    "2p_0n_0gr_0gc": 1,
    "4p_0n_0gr_0gc": 1,
    "6p_0n_0gr_0gc": 1,
    "6p_0n_7gr_0gc": 1,
    "7p_0n_7gr_0gc": 1
  },
  "target_ticker_counts": {
    "BE": 1,
    "ISRG": 1,
    "MU": 2,
    "PLTR": 3
  }
}
```

## Selection

```json
{
  "adjusted_trade_count": 3,
  "by_ticker_count": {
    "ISRG": 1,
    "MU": 2
  },
  "by_ticker_incremental_pnl": {
    "ISRG": 346.18,
    "MU": 2678.24
  },
  "by_window_count": {
    "late_strong": 1,
    "mid_weak": 1,
    "old_thin": 1
  },
  "by_window_incremental_pnl": {
    "late_strong": 1832.69,
    "mid_weak": 346.18,
    "old_thin": 845.55
  },
  "max_single_positive_incremental_pnl": 2678.24,
  "max_single_positive_pnl_share": 0.8855,
  "pnl_hhi_concentration": 0.7973,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "ISRG": 346.18,
    "MU": 2678.24
  },
  "positive_incremental_pnl": 3024.42,
  "sample_rows": [
    {
      "adjusted_pnl": 5498.06,
      "baseline_pnl": 3665.37,
      "entry_date": "2025-12-22",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+clean_positive_earnings_release_scalar",
      "event_notional_scalar": 1.6500000000000001,
      "exit_date": "2026-01-07",
      "form_base": "8-K",
      "incremental_pnl": 1832.69,
      "language_bucket": "positive_language",
      "notional": 24750.0,
      "spy_t1_return": 0.009063,
      "t1_excess_return_vs_spy": 0.060822,
      "t1_return": 0.069885,
      "text_event_type": "earnings_release_text",
      "ticker": "MU",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 1038.55,
      "baseline_pnl": 692.37,
      "entry_date": "2025-04-25",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+clean_positive_earnings_release_scalar",
      "event_notional_scalar": 1.6500000000000001,
      "exit_date": "2025-05-09",
      "form_base": "8-K",
      "incremental_pnl": 346.18,
      "language_bucket": "positive_language",
      "notional": 24750.0,
      "spy_t1_return": 0.021049,
      "t1_excess_return_vs_spy": 0.02035,
      "t1_return": 0.041399,
      "text_event_type": "earnings_release_text",
      "ticker": "ISRG",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 2536.65,
      "baseline_pnl": 1691.1,
      "entry_date": "2024-12-23",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+clean_positive_earnings_release_scalar",
      "event_notional_scalar": 1.6500000000000001,
      "exit_date": "2025-01-08",
      "form_base": "8-K",
      "incremental_pnl": 845.55,
      "language_bucket": "positive_language",
      "notional": 24750.0,
      "spy_t1_return": 0.012011,
      "t1_excess_return_vs_spy": 0.02278,
      "t1_return": 0.034792,
      "text_event_type": "earnings_release_text",
      "ticker": "MU",
      "window": "old_thin"
    }
  ],
  "windows_present": 3
}
```

No JavaScript was used.
