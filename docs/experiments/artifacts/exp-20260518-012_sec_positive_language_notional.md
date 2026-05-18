# exp-20260518-012 SEC Positive-Language Notional

Decision: `rejected_sec_positive_language_notional`.

## Hypothesis

Inside the accepted SEC financial-report T+1 paper sleeve, covered positive_language filings may have a distinct continuation profile after positive T+1 confirmation. A bounded paper-notional scalar should improve replacement value without changing SEC queue eligibility, capacity, or live orders.

## Best Variant

- best_variant: `positive_language_scalar_0.25`
- positive_language_scalar: `0.25`
- EV delta: `0.016479`
- PnL delta: `$-478.05`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta | Positive trades | Positive PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | +0.0393 | $-213.70 | +0.0001 | 2 | $-213.71 |
| mid_weak | -0.0354 | $-513.91 | +0.0007 | 3 | $-513.91 |
| old_thin | +0.0126 | $+249.56 | -0.0001 | 3 | $+249.57 |

## Selection

```json
{
  "adjusted_trade_count": 8,
  "by_ticker_count": {
    "AVGO": 2,
    "DDOG": 2,
    "ISRG": 1,
    "MU": 2,
    "TSLA": 1
  },
  "by_ticker_incremental_pnl": {
    "AVGO": 777.79,
    "DDOG": 1881.41,
    "ISRG": -472.07,
    "MU": -3652.14,
    "TSLA": 986.96
  },
  "by_window_count": {
    "late_strong": 2,
    "mid_weak": 3,
    "old_thin": 3
  },
  "by_window_incremental_pnl": {
    "late_strong": -213.71,
    "mid_weak": -513.91,
    "old_thin": 249.57
  },
  "max_single_positive_incremental_pnl": 2285.41,
  "max_single_positive_pnl_share": 0.5643,
  "positive_incremental_pnl": 4050.16,
  "sample_rows": [
    {
      "adjusted_pnl": -761.8,
      "baseline_pnl": -3047.21,
      "entry_date": "2025-11-11",
      "event_family": "earnings_8k",
      "exit_date": "2025-11-25",
      "form_base": "8-K",
      "incremental_pnl": 2285.41,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.028738,
      "ticker": "DDOG",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 833.04,
      "baseline_pnl": 3332.16,
      "entry_date": "2025-12-22",
      "event_family": "earnings_8k",
      "exit_date": "2026-01-07",
      "form_base": "8-K",
      "incremental_pnl": -2499.12,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.060822,
      "ticker": "MU",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": 157.36,
      "baseline_pnl": 629.43,
      "entry_date": "2025-04-25",
      "event_family": "earnings_8k",
      "exit_date": "2025-05-09",
      "form_base": "8-K",
      "incremental_pnl": -472.07,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.02035,
      "ticker": "ISRG",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": 134.67,
      "baseline_pnl": 538.67,
      "entry_date": "2025-05-09",
      "event_family": "earnings_8k",
      "exit_date": "2025-05-23",
      "form_base": "8-K",
      "incremental_pnl": -404.0,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.023215,
      "ticker": "DDOG",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -120.72,
      "baseline_pnl": -482.88,
      "entry_date": "2025-09-09",
      "event_family": "earnings_8k",
      "exit_date": "2025-09-23",
      "form_base": "8-K",
      "incremental_pnl": 362.16,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.029673,
      "ticker": "AVGO",
      "window": "mid_weak"
    },
    {
      "adjusted_pnl": -138.54,
      "baseline_pnl": -554.17,
      "entry_date": "2024-12-17",
      "event_family": "earnings_8k",
      "exit_date": "2025-01-02",
      "form_base": "8-K",
      "incremental_pnl": 415.63,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.10783,
      "ticker": "AVGO",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 384.34,
      "baseline_pnl": 1537.36,
      "entry_date": "2024-12-23",
      "event_family": "earnings_8k",
      "exit_date": "2025-01-08",
      "form_base": "8-K",
      "incremental_pnl": -1153.02,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.02278,
      "ticker": "MU",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": -328.99,
      "baseline_pnl": -1315.95,
      "entry_date": "2025-02-03",
      "event_family": "earnings_8k",
      "exit_date": "2025-02-18",
      "form_base": "8-K",
      "incremental_pnl": 986.96,
      "language_bucket": "positive_language",
      "t1_excess_return_vs_spy": 0.016114,
      "ticker": "TSLA",
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
