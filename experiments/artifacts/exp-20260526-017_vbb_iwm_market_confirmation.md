# exp-20260526-017 VBB IWM Market-Participation Confirmation

Decision: `rejected_vbb_iwm_market_participation_confirmation`.

Single variable: on top of the accepted exp-20260526-014 VBB paper adapter, keep selected paper notional only when IWM 20-day return is greater than SPY 20-day return on the signal date.

## Three-Window Result Versus Exp014

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Kept / Before Trades | Removed PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5780 | 5.5267 | -0.0513 | $121,255.25 | $120,669.27 | $-585.98 | +0.0003 | 4/8 | $+585.98 |
| mid_weak | 2.2780 | 2.2320 | -0.0460 | $80,780.62 | $80,000.39 | $-780.23 | +0.0000 | 14/17 | $+780.23 |
| old_thin | 0.7505 | 0.8047 | +0.0542 | $46,040.62 | $47,902.14 | $+1,861.52 | -0.0018 | 11/22 | $-1,861.52 |

## Aggregate

- EV delta vs exp014: `-0.0431` (`-0.005008`)
- PnL delta vs exp014: `$495.31` (`0.001997`)
- kept trades: `29`
- max drawdown drift: `0.0003`

## Gate 4

```json
{
  "aggregate": {
    "after_expected_value_score_sum": 8.5634,
    "after_total_pnl_sum": 248571.8,
    "baseline_expected_value_score_sum": 8.6065,
    "baseline_total_pnl_sum": 248076.49,
    "expected_value_score_delta_pct": -0.005008,
    "expected_value_score_delta_sum": -0.0431,
    "max_drawdown_delta_max": 0.0003,
    "target_trade_count_sum": 29,
    "total_pnl_delta_pct": 0.001997,
    "total_pnl_delta_sum": 495.31,
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_improved": 1,
    "windows_pnl_regressed": 2
  },
  "concentration_passed": true,
  "drawdown_guard": {
    "max_allowed_worse": 0.005,
    "observed_max_delta": 0.0003
  },
  "failed_reasons": [
    "aggregate_ev_not_positive_vs_exp014",
    "window_ev_regression_vs_exp014",
    "window_pnl_regression_vs_exp014",
    "target_sample_too_small"
  ],
  "passed": false,
  "target_trade_summary": {
    "by_ticker_count": {
      "AMD": 1,
      "AMZN": 3,
      "APP": 3,
      "BKNG": 1,
      "COIN": 4,
      "CRDO": 1,
      "DE": 1,
      "GE": 1,
      "GS": 2,
      "MA": 1,
      "MSFT": 1,
      "MU": 3,
      "NFLX": 1,
      "PLTR": 1,
      "SNOW": 1,
      "SPOT": 1,
      "TRIP": 1,
      "TSLA": 1,
      "UNH": 1
    },
    "by_ticker_pnl": {
      "AMD": -385.62,
      "AMZN": 107.05,
      "APP": 3435.04,
      "BKNG": 277.04,
      "COIN": 3966.51,
      "CRDO": 1364.5,
      "DE": -322.4,
      "GE": 266.16,
      "GS": -155.79,
      "MA": -0.88,
      "MSFT": 111.72,
      "MU": 3319.31,
      "NFLX": 510.92,
      "PLTR": 1738.4,
      "SNOW": 448.23,
      "SPOT": -955.91,
      "TRIP": -219.06,
      "TSLA": 135.59,
      "UNH": 80.0
    },
    "by_window_pnl": {
      "late_strong": 3596.35,
      "mid_weak": 1890.28,
      "old_thin": 8234.18
    },
    "max_single_positive_pnl_share": 0.251675,
    "positive_by_ticker_pnl": {
      "AMZN": 107.05,
      "APP": 3435.04,
      "BKNG": 277.04,
      "COIN": 3966.51,
      "CRDO": 1364.5,
      "GE": 266.16,
      "MSFT": 111.72,
      "MU": 3319.31,
      "NFLX": 510.92,
      "PLTR": 1738.4,
      "SNOW": 448.23,
      "TSLA": 135.59,
      "UNH": 80.0
    },
    "positive_pnl_hhi": 0.177512,
    "total_pnl": 13720.81,
    "total_trade_count": 29,
    "windows_with_target_trades": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  }
}
```

## Market Context Audit

```json
{
  "late_strong": {
    "before_vbb_trade_count": 8,
    "confirmed_dates": [
      "2025-12-10",
      "2025-12-19",
      "2026-01-06",
      "2026-01-22"
    ],
    "confirmed_pnl": 3596.35,
    "confirmed_trade_count": 4,
    "filtered_candidate_sample_count": 22,
    "raw_candidate_count": 30,
    "removed_dates": [
      "2025-10-29",
      "2025-11-05",
      "2025-11-12",
      "2026-01-05"
    ],
    "removed_pnl": 585.98,
    "removed_trade_count": 4
  },
  "mid_weak": {
    "before_vbb_trade_count": 17,
    "confirmed_dates": [
      "2025-05-08",
      "2025-05-12",
      "2025-05-13",
      "2025-05-14",
      "2025-06-23",
      "2025-06-24",
      "2025-06-26",
      "2025-06-27",
      "2025-06-30",
      "2025-09-04",
      "2025-09-09",
      "2025-09-16",
      "2025-09-18",
      "2025-09-19"
    ],
    "confirmed_pnl": 1890.28,
    "confirmed_trade_count": 14,
    "filtered_candidate_sample_count": 61,
    "raw_candidate_count": 78,
    "removed_dates": [
      "2025-06-16",
      "2025-08-06",
      "2025-10-01"
    ],
    "removed_pnl": 780.23,
    "removed_trade_count": 3
  },
  "old_thin": {
    "before_vbb_trade_count": 22,
    "confirmed_dates": [
      "2024-11-01",
      "2024-11-05",
      "2024-11-06",
      "2024-11-07",
      "2024-11-08",
      "2024-11-21",
      "2024-11-25",
      "2025-01-21",
      "2025-01-22",
      "2025-01-23",
      "2025-01-30"
    ],
    "confirmed_pnl": 8234.18,
    "confirmed_trade_count": 11,
    "filtered_candidate_sample_count": 64,
    "raw_candidate_count": 86,
    "removed_dates": [
      "2024-10-16",
      "2024-10-29",
      "2024-12-16",
      "2024-12-20",
      "2025-01-06",
      "2025-01-15",
      "2025-01-17",
      "2025-01-28",
      "2025-02-04",
      "2025-02-06",
      "2025-02-28"
    ],
    "removed_pnl": -1861.52,
    "removed_trade_count": 11
  }
}
```

## Production Impact

Replay-only/default-off paper scout. No shared policy, production adapter, run adapter, backtester adapter, watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
