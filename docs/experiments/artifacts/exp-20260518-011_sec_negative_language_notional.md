# exp-20260518-011 SEC Negative-Language Notional

Decision: `rejected_sec_negative_language_notional`.

## Hypothesis

Inside the accepted SEC financial-report T+1 paper sleeve, covered negative_language filings may have a distinct continuation profile after positive T+1 confirmation. A bounded paper-notional scalar should improve replacement value without changing SEC queue eligibility, capacity, or live orders.

## Best Variant

- best_variant: `negative_language_scalar_1.50`
- negative_language_scalar: `1.5`
- EV delta: `0.110954`
- PnL delta: `$1469.9`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta | Negative trades | Negative PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | +0.0211 | $+191.89 | -0.0001 | 1 | $+191.88 |
| mid_weak | +0.1073 | $+1,794.32 | -0.0007 | 2 | $+1,794.32 |
| old_thin | -0.0175 | $-516.31 | +0.0024 | 4 | $-516.31 |

## Selection

```json
{
  "adjusted_trade_count": 7,
  "by_ticker_count": {
    "CRDO": 2,
    "DE": 3,
    "GS": 1,
    "MCD": 1
  },
  "by_ticker_incremental_pnl": {
    "CRDO": 1794.32,
    "DE": -435.25,
    "GS": 184.96,
    "MCD": -74.13
  },
  "by_window_count": {
    "late_strong": 1,
    "mid_weak": 2,
    "old_thin": 4
  },
  "by_window_incremental_pnl": {
    "late_strong": 191.89,
    "mid_weak": 1794.32,
    "old_thin": -516.31
  },
  "max_single_positive_incremental_pnl": 1004.63,
  "max_single_positive_pnl_share": 0.4627,
  "positive_incremental_pnl": 2171.17,
  "sample_rows": [
    {
      "adjusted_pnl": 575.66,
      "baseline_pnl": 383.78,
      "entry_date": "2025-12-02",
      "event_family": "earnings_8k",
      "exit_date": "2025-12-16",
      "form_base": "8-K",
      "incremental_pnl": 191.89,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.012359,
      "ticker": "DE",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 2369.06,
      "baseline_pnl": 1579.37,
      "entry_date": "2025-06-05",
      "event_family": "earnings_8k",
      "exit_date": "2025-06-20",
      "form_base": "8-K",
      "incremental_pnl": 789.69,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.063394,
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 3013.89,
      "baseline_pnl": 2009.26,
      "entry_date": "2025-09-08",
      "event_family": "earnings_8k",
      "exit_date": "2025-09-22",
      "form_base": "8-K",
      "incremental_pnl": 1004.63,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.053792,
      "ticker": "CRDO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -222.38,
      "baseline_pnl": -148.25,
      "entry_date": "2024-11-01",
      "event_family": "earnings_8k",
      "exit_date": "2024-11-15",
      "form_base": "8-K",
      "incremental_pnl": -74.13,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.021627,
      "ticker": "MCD",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -502.99,
      "baseline_pnl": -335.33,
      "entry_date": "2024-11-26",
      "event_family": "earnings_8k",
      "exit_date": "2024-12-11",
      "form_base": "8-K",
      "incremental_pnl": -167.66,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.03252,
      "ticker": "DE",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 554.87,
      "baseline_pnl": 369.91,
      "entry_date": "2025-01-21",
      "event_family": "earnings_8k",
      "exit_date": "2025-02-04",
      "form_base": "8-K",
      "incremental_pnl": 184.96,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.011086,
      "ticker": "GS",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -1378.43,
      "baseline_pnl": -918.95,
      "entry_date": "2025-02-19",
      "event_family": "earnings_8k",
      "exit_date": "2025-03-05",
      "form_base": "8-K",
      "incremental_pnl": -459.48,
      "language_bucket": "negative_language",
      "t1_excess_return_vs_spy": 0.041502,
      "ticker": "DE",
      "window": "old_thin"
    }
  ],
  "windows_present": 3
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "parity_test_added": false,
  "promotion_requirement": "If accepted, move rule to shared SEC paper sleeve before final decision.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
