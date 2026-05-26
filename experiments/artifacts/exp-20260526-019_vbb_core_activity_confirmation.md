# exp-20260526-019 VBB Same-Day Core-Activity Confirmation

Decision: `rejected_vbb_same_day_core_activity_support`.

Single variable: on top of the accepted exp-20260526-014 VBB paper adapter, selected VBB paper trades get 1.10x paper-notional support only when the canonical core engine also entered at least one trade on the same signal date.

## Three-Window Result Versus Exp014

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5780 | 5.5821 | +0.0041 | $121,255.25 | $121,352.28 | $+97.03 | -0.0001 | 2/8 | $+97.03 |
| mid_weak | 2.2780 | 2.2749 | -0.0031 | $80,780.62 | $80,673.81 | $-106.81 | +0.0001 | 5/17 | $-106.81 |
| old_thin | 0.7505 | 0.7503 | -0.0002 | $46,040.62 | $46,026.86 | $-13.76 | +0.0000 | 4/22 | $-13.76 |

## Aggregate

- EV delta vs exp014: `0.0008` (`9.3e-05`)
- PnL delta vs exp014: `$-23.54` (`-9.5e-05`)
- adjusted trades: `11`
- max drawdown drift: `0.0001`

## Gate 4

```json
{
  "aggregate": {
    "after_expected_value_score_sum": 8.6073,
    "after_total_pnl_sum": 248052.95,
    "baseline_expected_value_score_sum": 8.6065,
    "baseline_total_pnl_sum": 248076.49,
    "expected_value_score_delta_pct": 9.3e-05,
    "expected_value_score_delta_sum": 0.0008,
    "max_drawdown_delta_max": 0.0001,
    "target_trade_count_sum": 11,
    "total_pnl_delta_pct": -9.5e-05,
    "total_pnl_delta_sum": -23.54,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_improved": 1,
    "windows_pnl_regressed": 2
  },
  "concentration_passed": false,
  "drawdown_guard": {
    "max_allowed_worse": 0.005,
    "observed_max_delta": 0.0001
  },
  "failed_reasons": [
    "aggregate_pnl_not_positive_vs_exp014",
    "window_ev_regression_vs_exp014",
    "window_pnl_regression_vs_exp014",
    "target_concentration_failed"
  ],
  "passed": false,
  "target_trade_summary": {
    "by_ticker_count": {
      "AMD": 1,
      "AMZN": 1,
      "DE": 1,
      "MCD": 1,
      "MSFT": 1,
      "MU": 2,
      "SPOT": 1,
      "TRIP": 1,
      "TSLA": 1,
      "UNH": 1
    },
    "by_ticker_pnl": {
      "AMD": -38.56,
      "AMZN": 26.83,
      "DE": -32.24,
      "MCD": 8.17,
      "MSFT": 11.17,
      "MU": 97.03,
      "SPOT": -95.59,
      "TRIP": -21.91,
      "TSLA": 13.56,
      "UNH": 8.0
    },
    "by_window_pnl": {
      "late_strong": 97.03,
      "mid_weak": -106.81,
      "old_thin": -13.76
    },
    "max_single_positive_pnl_share": 0.588917,
    "positive_by_ticker_pnl": {
      "AMZN": 26.83,
      "MCD": 8.17,
      "MSFT": 11.17,
      "MU": 97.03,
      "TSLA": 13.56,
      "UNH": 8.0
    },
    "positive_pnl_hhi": 0.389528,
    "total_pnl": -23.54,
    "total_trade_count": 11,
    "windows_with_target_trades": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  }
}
```

## Core Activity Audit

```json
{
  "late_strong": {
    "adjusted_dates": [
      "2026-01-06",
      "2026-01-22"
    ],
    "adjusted_source_pnl": 970.3,
    "adjusted_tickers": [
      "MU"
    ],
    "adjusted_trade_count": 2,
    "before_vbb_trade_count": 8,
    "filtered_candidate_sample_count": 22,
    "incremental_pnl": 97.03,
    "raw_candidate_count": 30,
    "unadjusted_trade_count": 6
  },
  "mid_weak": {
    "adjusted_dates": [
      "2025-05-14",
      "2025-06-23",
      "2025-06-26",
      "2025-08-06",
      "2025-09-09"
    ],
    "adjusted_source_pnl": -1068.1,
    "adjusted_tickers": [
      "AMD",
      "MCD",
      "MSFT",
      "SPOT",
      "UNH"
    ],
    "adjusted_trade_count": 5,
    "before_vbb_trade_count": 17,
    "filtered_candidate_sample_count": 61,
    "incremental_pnl": -106.81,
    "raw_candidate_count": 78,
    "unadjusted_trade_count": 12
  },
  "old_thin": {
    "adjusted_dates": [
      "2024-11-01",
      "2024-11-08",
      "2024-11-25",
      "2025-01-23"
    ],
    "adjusted_source_pnl": -137.6,
    "adjusted_tickers": [
      "AMZN",
      "DE",
      "TRIP",
      "TSLA"
    ],
    "adjusted_trade_count": 4,
    "before_vbb_trade_count": 22,
    "filtered_candidate_sample_count": 64,
    "incremental_pnl": -13.76,
    "raw_candidate_count": 86,
    "unadjusted_trade_count": 18
  }
}
```

## Production Impact

Replay-only/default-off paper scout. No shared policy, production adapter, run adapter, backtester adapter, watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
