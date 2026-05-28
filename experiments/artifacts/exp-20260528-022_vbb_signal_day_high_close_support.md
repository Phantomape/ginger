# exp-20260528-022 VBB Signal-Day High-Close Support

Decision: `accepted_shared_vbb_signal_day_high_close_support`.

Single variable: on top of the current accepted VBB paper adapter, selected VBB paper trades receive small default-off paper notional support when signal-day close-location value clears the best predeclared threshold.

Best variant: `close_location_gte_0p70_scalar_1p10`.

## Three-Window Result Versus Current VBB

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6007 | 5.6272 | +0.0265 | $121,488.20 | $121,801.67 | $+313.47 | -0.0002 | 7/8 | $+313.47 |
| mid_weak | 2.2920 | 2.2943 | +0.0023 | $80,990.62 | $81,070.27 | $+79.65 | +0.0000 | 11/17 | $+79.65 |
| old_thin | 0.7613 | 0.7646 | +0.0033 | $46,424.76 | $46,621.73 | $+196.97 | +0.0005 | 16/22 | $+196.97 |

## Aggregate

- EV delta vs current VBB: `0.0321` (`0.003709`)
- PnL delta vs current VBB: `$590.09` (`0.002371`)
- adjusted trades: `34`
- max drawdown drift: `0.0005`

## Variant Sweep

```json
[
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6843,
      "after_total_pnl_sum": 249395.4,
      "baseline_expected_value_score_sum": 8.654,
      "baseline_total_pnl_sum": 248903.58,
      "expected_value_score_delta_pct": 0.003501,
      "expected_value_score_delta_sum": 0.0303,
      "max_drawdown_delta_max": 0.0002,
      "target_trade_count_sum": 38,
      "total_pnl_delta_pct": 0.001976,
      "total_pnl_delta_sum": 491.82,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.302904,
    "min_close_location": 0.6,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.220439,
    "target_trade_count": 38,
    "variant_id": "close_location_gte_0p60_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6758,
      "after_total_pnl_sum": 249198.62,
      "baseline_expected_value_score_sum": 8.654,
      "baseline_total_pnl_sum": 248903.58,
      "expected_value_score_delta_pct": 0.002519,
      "expected_value_score_delta_sum": 0.0218,
      "max_drawdown_delta_max": 0.0002,
      "target_trade_count_sum": 34,
      "total_pnl_delta_pct": 0.001185,
      "total_pnl_delta_sum": 295.04,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.339991,
    "min_close_location": 0.7,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.246012,
    "target_trade_count": 34,
    "variant_id": "close_location_gte_0p70_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6861,
      "after_total_pnl_sum": 249493.67,
      "baseline_expected_value_score_sum": 8.654,
      "baseline_total_pnl_sum": 248903.58,
      "expected_value_score_delta_pct": 0.003709,
      "expected_value_score_delta_sum": 0.0321,
      "max_drawdown_delta_max": 0.0005,
      "target_trade_count_sum": 34,
      "total_pnl_delta_pct": 0.002371,
      "total_pnl_delta_sum": 590.09,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.340004,
    "min_close_location": 0.7,
    "notional_scalar": 1.1,
    "positive_pnl_hhi": 0.246016,
    "target_trade_count": 34,
    "variant_id": "close_location_gte_0p70_scalar_1p10"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6755,
      "after_total_pnl_sum": 249167.3,
      "baseline_expected_value_score_sum": 8.654,
      "baseline_total_pnl_sum": 248903.58,
      "expected_value_score_delta_pct": 0.002484,
      "expected_value_score_delta_sum": 0.0215,
      "max_drawdown_delta_max": 0.0003,
      "target_trade_count_sum": 26,
      "total_pnl_delta_pct": 0.00106,
      "total_pnl_delta_sum": 263.72,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.374987,
    "min_close_location": 0.8,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.29545,
    "target_trade_count": 26,
    "variant_id": "close_location_gte_0p80_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6843,
      "after_total_pnl_sum": 249431.02,
      "baseline_expected_value_score_sum": 8.654,
      "baseline_total_pnl_sum": 248903.58,
      "expected_value_score_delta_pct": 0.003501,
      "expected_value_score_delta_sum": 0.0303,
      "max_drawdown_delta_max": 0.0005,
      "target_trade_count_sum": 26,
      "total_pnl_delta_pct": 0.002119,
      "total_pnl_delta_sum": 527.44,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.375001,
    "min_close_location": 0.8,
    "notional_scalar": 1.1,
    "positive_pnl_hhi": 0.295456,
    "target_trade_count": 26,
    "variant_id": "close_location_gte_0p80_scalar_1p10"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6579,
      "after_total_pnl_sum": 249065.21,
      "baseline_expected_value_score_sum": 8.654,
      "baseline_total_pnl_sum": 248903.58,
      "expected_value_score_delta_pct": 0.000451,
      "expected_value_score_delta_sum": 0.0039,
      "max_drawdown_delta_max": 0.0002,
      "target_trade_count_sum": 13,
      "total_pnl_delta_pct": 0.000649,
      "total_pnl_delta_sum": 161.63,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 1,
      "windows_pnl_improved": 2,
      "windows_pnl_regressed": 1
    },
    "failed_reasons": [
      "window_ev_regression_vs_current_vbb",
      "window_pnl_regression_vs_current_vbb",
      "target_concentration_failed"
    ],
    "gate4_passed": false,
    "max_single_positive_pnl_share": 0.58787,
    "min_close_location": 0.9,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.404955,
    "target_trade_count": 13,
    "variant_id": "close_location_gte_0p90_scalar_1p05"
  }
]
```

## Gate 4

```json
{
  "aggregate": {
    "after_expected_value_score_sum": 8.6861,
    "after_total_pnl_sum": 249493.67,
    "baseline_expected_value_score_sum": 8.654,
    "baseline_total_pnl_sum": 248903.58,
    "expected_value_score_delta_pct": 0.003709,
    "expected_value_score_delta_sum": 0.0321,
    "max_drawdown_delta_max": 0.0005,
    "target_trade_count_sum": 34,
    "total_pnl_delta_pct": 0.002371,
    "total_pnl_delta_sum": 590.09,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "concentration_passed": true,
  "drawdown_guard": {
    "max_allowed_worse": 0.005,
    "observed_max_delta": 0.0005
  },
  "failed_reasons": [],
  "passed": true,
  "target_trade_summary": {
    "by_ticker_count": {
      "AAPL": 1,
      "AMD": 1,
      "AMZN": 2,
      "APP": 1,
      "AVGO": 1,
      "BKNG": 1,
      "CAT": 1,
      "COIN": 4,
      "CVX": 1,
      "DDOG": 1,
      "DE": 2,
      "DIS": 1,
      "GE": 1,
      "GOOG": 1,
      "GS": 1,
      "ISRG": 1,
      "LLY": 1,
      "MSFT": 1,
      "MU": 3,
      "PLTR": 2,
      "SNOW": 1,
      "SPOT": 1,
      "TRIP": 1,
      "TSLA": 1,
      "UNH": 1,
      "V": 1
    },
    "by_ticker_pnl": {
      "AAPL": -59.13,
      "AMD": 59.38,
      "AMZN": -15.6,
      "APP": 55.7,
      "AVGO": -38.49,
      "BKNG": 27.7,
      "CAT": -12.92,
      "COIN": 354.93,
      "CVX": -2.15,
      "DDOG": -23.34,
      "DE": -19.84,
      "DIS": -54.59,
      "GE": 26.62,
      "GOOG": 0.48,
      "GS": -3.67,
      "ISRG": -8.65,
      "LLY": 10.48,
      "MSFT": 11.17,
      "MU": 355.43,
      "PLTR": 77.1,
      "SNOW": 44.82,
      "SPOT": -95.59,
      "TRIP": -21.91,
      "TSLA": 13.56,
      "UNH": 8.0,
      "V": -99.4
    },
    "by_window_pnl": {
      "late_strong": 313.47,
      "mid_weak": 79.65,
      "old_thin": 196.97
    },
    "max_single_positive_pnl_share": 0.340004,
    "positive_by_ticker_pnl": {
      "AMD": 59.38,
      "APP": 55.7,
      "BKNG": 27.7,
      "COIN": 354.93,
      "GE": 26.62,
      "GOOG": 0.48,
      "LLY": 10.48,
      "MSFT": 11.17,
      "MU": 355.43,
      "PLTR": 77.1,
      "SNOW": 44.82,
      "TSLA": 13.56,
      "UNH": 8.0
    },
    "positive_pnl_hhi": 0.246016,
    "total_pnl": 590.09,
    "total_trade_count": 34,
    "windows_with_target_trades": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  }
}
```

## High-Close Audit

```json
{
  "late_strong": {
    "adjusted_close_location_max": 0.990412,
    "adjusted_close_location_min": 0.70497,
    "adjusted_dates": [
      "2025-10-29",
      "2025-11-12",
      "2025-12-10",
      "2025-12-19",
      "2026-01-05",
      "2026-01-06",
      "2026-01-22"
    ],
    "adjusted_incremental_pnl": 313.47,
    "adjusted_tickers": [
      "BKNG",
      "CAT",
      "CVX",
      "DIS",
      "MU"
    ],
    "adjusted_trade_count": 7,
    "all_selected_close_location_max": 0.990412,
    "all_selected_close_location_min": 0.377101,
    "before_vbb_trade_count": 8,
    "snapshot_ticker_count": 56,
    "unadjusted_trade_count": 1
  },
  "mid_weak": {
    "adjusted_close_location_max": 1.0,
    "adjusted_close_location_min": 0.700002,
    "adjusted_dates": [
      "2025-05-13",
      "2025-06-16",
      "2025-06-23",
      "2025-06-24",
      "2025-06-26",
      "2025-06-27",
      "2025-09-04",
      "2025-09-09",
      "2025-09-16",
      "2025-09-19",
      "2025-10-01"
    ],
    "adjusted_incremental_pnl": 79.65,
    "adjusted_tickers": [
      "AMD",
      "AMZN",
      "APP",
      "COIN",
      "GE",
      "LLY",
      "MSFT",
      "SPOT",
      "UNH"
    ],
    "adjusted_trade_count": 11,
    "all_selected_close_location_max": 1.0,
    "all_selected_close_location_min": 0.190557,
    "before_vbb_trade_count": 17,
    "snapshot_ticker_count": 52,
    "unadjusted_trade_count": 6
  },
  "old_thin": {
    "adjusted_close_location_max": 0.990566,
    "adjusted_close_location_min": 0.704715,
    "adjusted_dates": [
      "2024-10-16",
      "2024-10-29",
      "2024-11-05",
      "2024-11-06",
      "2024-11-08",
      "2024-11-21",
      "2024-11-25",
      "2024-12-16",
      "2024-12-20",
      "2025-01-15",
      "2025-01-17",
      "2025-01-21",
      "2025-01-23",
      "2025-01-28",
      "2025-02-06",
      "2025-02-28"
    ],
    "adjusted_incremental_pnl": 196.97,
    "adjusted_tickers": [
      "AAPL",
      "AVGO",
      "COIN",
      "DDOG",
      "DE",
      "GOOG",
      "GS",
      "ISRG",
      "PLTR",
      "SNOW",
      "TRIP",
      "TSLA",
      "V"
    ],
    "adjusted_trade_count": 16,
    "all_selected_close_location_max": 0.990566,
    "all_selected_close_location_min": 0.066958,
    "before_vbb_trade_count": 22,
    "snapshot_ticker_count": 52,
    "unadjusted_trade_count": 6
  }
}
```

## Production Impact

Accepted only into the shared default-off VBB paper adapter. No live orders, core universe, core ranking, core sizing, exits, LLM/news, or trade-enabled behavior changed.

No JavaScript was used.
