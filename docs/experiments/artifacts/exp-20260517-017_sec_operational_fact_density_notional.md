# exp-20260517-017 SEC Operational Fact Density Notional

- decision: `rejected_operational_fact_density_notional`
- status: `rejected`
- expected_value_score_delta: `-0.016569`
- total_pnl_delta: `-358.76`
- adjusted_trades: `9`

## Hypothesis

Inside the SEC financial-report T+1 paper sleeve, filings with high operational fact density and without high narrative vagueness should carry higher-quality continuation alpha than the undifferentiated sleeve.

## Aggregate Delta

```json
{
  "expected_value_score_sum_delta": -0.016569,
  "expected_value_score_sum_delta_pct": -0.002015,
  "max_drawdown_pct_max_delta": 0.000705,
  "max_drawdown_pct_max_delta_pct": 0.004322,
  "min_survival_rate_delta": 0.0,
  "min_survival_rate_delta_pct": 0.0,
  "sleeve_closed_trade_count_sum_delta": 0.0,
  "sleeve_closed_trade_count_sum_delta_pct": 0.0,
  "sleeve_total_pnl_sum_delta": -358.76,
  "sleeve_total_pnl_sum_delta_pct": -0.028893,
  "total_pnl_sum_delta": -358.76,
  "total_pnl_sum_delta_pct": -0.001439,
  "trade_count_sum_delta": 0.0,
  "trade_count_sum_delta_pct": 0.0
}
```

## Window Delta

```json
{
  "late_strong": {
    "expected_value_score": -0.00665,
    "total_pnl": -66.62,
    "max_drawdown_pct": 0.000584,
    "sharpe_daily": -0.00335
  },
  "mid_weak": {
    "expected_value_score": -0.002235,
    "total_pnl": -28.76,
    "max_drawdown_pct": 0.0,
    "sharpe_daily": -0.001498
  },
  "old_thin": {
    "expected_value_score": -0.007684,
    "total_pnl": -263.38,
    "max_drawdown_pct": 0.000705,
    "sharpe_daily": -0.008727
  }
}
```

## Selection

```json
{
  "adjusted_trade_count": 9,
  "windows_present": 3,
  "by_window_count": {
    "late_strong": 2,
    "mid_weak": 2,
    "old_thin": 5
  },
  "by_window_incremental_pnl": {
    "late_strong": -37.82,
    "mid_weak": -28.76,
    "old_thin": -263.39
  },
  "by_ticker_count": {
    "DE": 2,
    "GS": 1,
    "JPM": 4,
    "TSLA": 2
  },
  "by_ticker_incremental_pnl": {
    "DE": -125.43,
    "GS": -21.89,
    "JPM": 26.96,
    "TSLA": -209.61
  },
  "max_single_positive_incremental_pnl": 40.14,
  "max_single_positive_pnl_share": 0.8205,
  "positive_incremental_pnl": 48.92,
  "sample_rows": [
    {
      "window": "late_strong",
      "ticker": "GS",
      "entry_date": "2026-01-13",
      "exit_date": "2026-01-28",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "low",
      "baseline_pnl": -218.92,
      "adjusted_pnl": -240.81,
      "incremental_pnl": -21.89
    },
    {
      "window": "late_strong",
      "ticker": "JPM",
      "entry_date": "2026-01-16",
      "exit_date": "2026-02-02",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "low",
      "baseline_pnl": -159.31,
      "adjusted_pnl": -175.25,
      "incremental_pnl": -15.93
    },
    {
      "window": "mid_weak",
      "ticker": "JPM",
      "entry_date": "2025-07-18",
      "exit_date": "2025-08-01",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "low",
      "baseline_pnl": -60.27,
      "adjusted_pnl": -66.3,
      "incremental_pnl": -6.03
    },
    {
      "window": "mid_weak",
      "ticker": "TSLA",
      "entry_date": "2025-10-07",
      "exit_date": "2025-10-21",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "low",
      "baseline_pnl": -227.35,
      "adjusted_pnl": -250.08,
      "incremental_pnl": -22.73
    },
    {
      "window": "old_thin",
      "ticker": "TSLA",
      "entry_date": "2024-10-07",
      "exit_date": "2024-10-21",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "low",
      "baseline_pnl": -1868.76,
      "adjusted_pnl": -2055.64,
      "incremental_pnl": -186.88
    },
    {
      "window": "old_thin",
      "ticker": "JPM",
      "entry_date": "2024-10-16",
      "exit_date": "2024-10-30",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "medium",
      "baseline_pnl": 87.83,
      "adjusted_pnl": 96.61,
      "incremental_pnl": 8.78
    },
    {
      "window": "old_thin",
      "ticker": "DE",
      "entry_date": "2024-11-26",
      "exit_date": "2024-12-11",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "negative_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "medium",
      "baseline_pnl": -335.33,
      "adjusted_pnl": -368.86,
      "incremental_pnl": -33.53
    },
    {
      "window": "old_thin",
      "ticker": "JPM",
      "entry_date": "2025-01-21",
      "exit_date": "2025-02-04",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "neutral_or_mixed_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "low",
      "baseline_pnl": 401.42,
      "adjusted_pnl": 441.56,
      "incremental_pnl": 40.14
    },
    {
      "window": "old_thin",
      "ticker": "DE",
      "entry_date": "2025-02-19",
      "exit_date": "2025-03-05",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "language_bucket": "negative_language",
      "operational_fact_density_bucket": "high",
      "narrative_vagueness_bucket": "medium",
      "baseline_pnl": -918.95,
      "adjusted_pnl": -1010.85,
      "incremental_pnl": -91.9
    }
  ]
}
```

## Decision

This unexplored playbook branch is now tested and rejected on the current SEC sleeve. High fact density without high vagueness did not identify better continuation rows; the cohort was small, finance-heavy, and aggregate negative even before concentration became the main concern.
