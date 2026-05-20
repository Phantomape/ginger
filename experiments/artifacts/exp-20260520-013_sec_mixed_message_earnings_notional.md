# exp-20260520-013 SEC Mixed-Message Earnings-Release Notional

Decision: `rejected_sec_mixed_message_earnings_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered earnings_release_text rows that contain both positive and negative phrase hits may encode mixed messages or fact/tone gaps. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, LLM authority, or live orders.

## Best Variant

- best_variant: `mixed_message_earnings_scalar_0_00`
- target_scalar: `0.0`
- EV delta: `0.549796`
- PnL delta: `$5375.21`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.5336 | $+4,371.37 | -0.0015 |
| mid_weak | -0.0592 | $-1,069.94 | +0.0005 |
| old_thin | +0.0754 | $+2,073.78 | -0.0010 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.549796,
    "expected_value_score_sum_delta_pct": 0.046343,
    "max_drawdown_pct_max_delta": -0.001047,
    "max_drawdown_pct_max_delta_pct": -0.008951,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 5375.21,
    "sleeve_total_pnl_sum_delta_pct": 0.061544,
    "total_pnl_sum_delta": 5375.21,
    "total_pnl_sum_delta_pct": 0.016578,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.53365,
      "max_drawdown_pct": -0.001479,
      "sharpe_daily": 0.250937,
      "total_pnl": 4371.37
    },
    "mid_weak": {
      "expected_value_score": -0.059209,
      "max_drawdown_pct": 0.000477,
      "sharpe_daily": -0.017179,
      "total_pnl": -1069.94
    },
    "old_thin": {
      "expected_value_score": 0.075355,
      "max_drawdown_pct": -0.001047,
      "sharpe_daily": 0.035561,
      "total_pnl": 2073.78
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
    "adjusted_trade_count": 10,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.000477,
    "max_single_positive_pnl_share": 0.4805,
    "pnl_hhi_concentration": 0.3273,
    "pnl_top_5_contribution_pct": 0.9787,
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

## Coverage

```json
{
  "aggregate": {
    "non_target": 90,
    "target": 18
  },
  "by_window": {
    "late_strong": {
      "candidate_count": 39,
      "target_count": 7
    },
    "mid_weak": {
      "candidate_count": 29,
      "target_count": 5
    },
    "old_thin": {
      "candidate_count": 40,
      "target_count": 6
    }
  },
  "target_definition": {
    "negative_phrase_hits_gte": 1,
    "positive_phrase_hits_gte": 1,
    "sec_text_coverage_status": "covered",
    "text_event_type": "earnings_release_text"
  },
  "target_hit_pair_counts": {
    "10p_10n": 1,
    "10p_4n": 1,
    "11p_12n": 1,
    "11p_8n": 1,
    "12p_14n": 1,
    "1p_1n": 2,
    "1p_4n": 2,
    "2p_3n": 1,
    "3p_20n": 2,
    "5p_6n": 1,
    "7p_1n": 2,
    "7p_4n": 1,
    "8p_3n": 1,
    "9p_11n": 1
  },
  "target_language_bucket_counts": {
    "negative_language": 6,
    "neutral_or_mixed_language": 6,
    "positive_language": 6
  }
}
```

## Selection

```json
{
  "adjusted_trade_count": 10,
  "by_ticker_count": {
    "AVGO": 2,
    "CRDO": 1,
    "DDOG": 2,
    "MCD": 1,
    "TRIP": 1,
    "TSLA": 3
  },
  "by_ticker_incremental_pnl": {
    "AVGO": 1140.75,
    "CRDO": 358.77,
    "DDOG": 2759.39,
    "MCD": 148.25,
    "TRIP": 185.41,
    "TSLA": 782.63
  },
  "by_window_count": {
    "late_strong": 4,
    "mid_weak": 3,
    "old_thin": 3
  },
  "by_window_incremental_pnl": {
    "late_strong": 4371.36,
    "mid_weak": -1069.94,
    "old_thin": 2073.78
  },
  "max_single_positive_incremental_pnl": 3351.93,
  "max_single_positive_pnl_share": 0.4805,
  "pnl_hhi_concentration": 0.3273,
  "pnl_top_5_contribution_pct": 0.9787,
  "positive_by_ticker_incremental_pnl": {
    "AVGO": 1140.75,
    "CRDO": 358.77,
    "DDOG": 3351.93,
    "MCD": 148.25,
    "TRIP": 185.41,
    "TSLA": 1791.2
  },
  "positive_incremental_pnl": 6976.31,
  "sample_rows": [
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -3351.93,
      "entry_date": "2025-11-11",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-11-25",
      "form_base": "8-K",
      "incremental_pnl": 3351.93,
      "language_bucket": "positive_language",
      "notional": 0.0,
      "spy_t1_return": 0.015604,
      "t1_excess_return_vs_spy": 0.028738,
      "t1_return": 0.044342,
      "text_event_type": "earnings_release_text",
      "ticker": "DDOG",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -475.25,
      "entry_date": "2026-02-02",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
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
      "baseline_pnl": -185.41,
      "entry_date": "2026-02-18",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2026-03-04",
      "form_base": "8-K",
      "incremental_pnl": 185.41,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.001613,
      "t1_excess_return_vs_spy": 0.095161,
      "t1_return": 0.096774,
      "text_event_type": "earnings_release_text",
      "ticker": "TRIP",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -358.77,
      "entry_date": "2026-03-05",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2026-03-19",
      "form_base": "8-K",
      "incremental_pnl": 358.77,
      "language_bucket": "neutral_or_mixed_language",
      "notional": 0.0,
      "spy_t1_return": 0.007055,
      "t1_excess_return_vs_spy": 0.046799,
      "t1_return": 0.053854,
      "text_event_type": "earnings_release_text",
      "ticker": "CRDO",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 0.0,
      "baseline_pnl": 592.54,
      "entry_date": "2025-05-09",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-05-23",
      "form_base": "8-K",
      "incremental_pnl": -592.54,
      "language_bucket": "positive_language",
      "notional": 0.0,
      "spy_t1_return": 0.006968,
      "t1_excess_return_vs_spy": 0.023215,
      "t1_return": 0.030183,
      "text_event_type": "earnings_release_text",
      "ticker": "DDOG",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 0.0,
      "baseline_pnl": 1008.57,
      "entry_date": "2025-07-28",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
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
      "baseline_pnl": -531.17,
      "entry_date": "2025-09-09",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-09-23",
      "form_base": "8-K",
      "incremental_pnl": 531.17,
      "language_bucket": "positive_language",
      "notional": 0.0,
      "spy_t1_return": 0.002457,
      "t1_excess_return_vs_spy": 0.029673,
      "t1_return": 0.03213,
      "text_event_type": "earnings_release_text",
      "ticker": "AVGO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -148.25,
      "entry_date": "2024-11-01",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+mixed_message_earnings_release_scalar",
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
      "baseline_pnl": -609.58,
      "entry_date": "2024-12-17",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+earnings_release_text_spy_t1_context_scalar+mixed_message_earnings_release_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-01-02",
      "form_base": "8-K",
      "incremental_pnl": 609.58,
      "language_bucket": "positive_language",
      "notional": 0.0,
      "spy_t1_return": 0.00427,
      "t1_excess_return_vs_spy": 0.10783,
      "t1_return": 0.1121,
      "text_event_type": "earnings_release_text",
      "ticker": "AVGO",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -1315.95,
      "entry_date": "2025-02-03",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+mixed_message_earnings_release_scalar",
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
    }
  ],
  "windows_present": 3
}
```

No JavaScript was used.
