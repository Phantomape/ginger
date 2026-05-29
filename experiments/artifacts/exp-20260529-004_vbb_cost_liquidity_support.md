# exp-20260529-004 VBB Cost/Liquidity Support

Decision: `accepted_shared_vbb_cost_liquidity_support`.

Single variable: on top of the current accepted VBB paper adapter, selected VBB paper trades receive small default-off paper notional support when signal-day dollar volume and daily range meet the best predeclared cost/liquidity bucket.

Best variant: `dvol_gte_200m_range_lte_0p10_scalar_1p05`.

## Three-Window Result Versus Current VBB

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.6272 | 5.6505 | +0.0233 | $121,801.67 | $122,038.10 | $+236.43 | -0.0001 | 8/8 | $+236.43 |
| mid_weak | 2.2943 | 2.2982 | +0.0039 | $81,070.27 | $81,207.55 | $+137.28 | +0.0000 | 15/17 | $+137.28 |
| old_thin | 0.7646 | 0.7659 | +0.0013 | $46,621.73 | $46,704.32 | $+82.59 | -0.0003 | 18/22 | $+82.59 |

## Aggregate

- EV delta vs current VBB: `0.0285` (`0.003281`)
- PnL delta vs current VBB: `$456.3` (`0.001829`)
- adjusted trades: `41`
- max drawdown drift: `0.0`

## Gate 4

```json
{
  "aggregate": {
    "after_expected_value_score_sum": 8.7146,
    "after_total_pnl_sum": 249949.97,
    "baseline_expected_value_score_sum": 8.6861,
    "baseline_total_pnl_sum": 249493.67,
    "expected_value_score_delta_pct": 0.003281,
    "expected_value_score_delta_sum": 0.0285,
    "max_drawdown_delta_max": 0.0,
    "target_trade_count_sum": 41,
    "total_pnl_delta_pct": 0.001829,
    "total_pnl_delta_sum": 456.3,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "concentration_passed": true,
  "drawdown_guard": {
    "max_allowed_worse": 0.005,
    "observed_max_delta": 0.0
  },
  "failed_reasons": [],
  "passed": true,
  "target_trade_summary": {
    "by_ticker_count": {
      "AAPL": 1,
      "AMD": 2,
      "AMZN": 3,
      "APP": 2,
      "AVGO": 1,
      "BKNG": 1,
      "CAT": 1,
      "COIN": 2,
      "CRDO": 1,
      "CVX": 1,
      "DDOG": 1,
      "DE": 2,
      "DIS": 1,
      "GE": 1,
      "GOOG": 1,
      "GS": 2,
      "ISRG": 1,
      "LLY": 2,
      "MA": 1,
      "MCD": 1,
      "MSFT": 1,
      "MU": 3,
      "NFLX": 1,
      "PLTR": 2,
      "SNOW": 1,
      "SPOT": 1,
      "TSLA": 1,
      "TSM": 1,
      "UNH": 1,
      "V": 1
    },
    "by_ticker_pnl": {
      "AAPL": -32.52,
      "AMD": 13.38,
      "AMZN": 4.83,
      "APP": 40.65,
      "AVGO": -21.17,
      "BKNG": 15.24,
      "CAT": -7.11,
      "COIN": 44.66,
      "CRDO": 75.05,
      "CVX": -1.18,
      "DDOG": -12.84,
      "DE": -10.92,
      "DIS": -30.03,
      "GE": 14.64,
      "GOOG": 0.27,
      "GS": -8.14,
      "ISRG": -4.76,
      "LLY": 69.79,
      "MA": -0.04,
      "MCD": 4.08,
      "MSFT": 6.14,
      "MU": 195.48,
      "NFLX": 25.55,
      "PLTR": 143.81,
      "SNOW": 24.65,
      "SPOT": -52.58,
      "TSLA": 7.46,
      "TSM": 2.18,
      "UNH": 4.4,
      "V": -54.67
    },
    "by_window_pnl": {
      "late_strong": 236.43,
      "mid_weak": 137.28,
      "old_thin": 82.59
    },
    "max_single_positive_pnl_share": 0.282379,
    "positive_by_ticker_pnl": {
      "AMD": 13.38,
      "AMZN": 4.83,
      "APP": 40.65,
      "BKNG": 15.24,
      "COIN": 44.66,
      "CRDO": 75.05,
      "GE": 14.64,
      "GOOG": 0.27,
      "LLY": 69.79,
      "MCD": 4.08,
      "MSFT": 6.14,
      "MU": 195.48,
      "NFLX": 25.55,
      "PLTR": 143.81,
      "SNOW": 24.65,
      "TSLA": 7.46,
      "TSM": 2.18,
      "UNH": 4.4
    },
    "positive_pnl_hhi": 0.156685,
    "total_pnl": 456.3,
    "total_trade_count": 41,
    "windows_with_target_trades": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  }
}
```

## Variant Sweep

```json
[
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.7111,
      "after_total_pnl_sum": 249789.19,
      "baseline_expected_value_score_sum": 8.6861,
      "baseline_total_pnl_sum": 249493.67,
      "expected_value_score_delta_pct": 0.002878,
      "expected_value_score_delta_sum": 0.025,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 35,
      "total_pnl_delta_pct": 0.001184,
      "total_pnl_delta_sum": 295.52,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [
      "window_ev_regression_vs_current_vbb"
    ],
    "gate4_passed": false,
    "max_range_pct": 0.08,
    "max_single_positive_pnl_share": 0.369116,
    "min_dollar_volume": 100000000.0,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.191635,
    "target_trade_count": 35,
    "variant_id": "dvol_gte_100m_range_lte_0p08_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.7356,
      "after_total_pnl_sum": 250084.76,
      "baseline_expected_value_score_sum": 8.6861,
      "baseline_total_pnl_sum": 249493.67,
      "expected_value_score_delta_pct": 0.005699,
      "expected_value_score_delta_sum": 0.0495,
      "max_drawdown_delta_max": -0.0001,
      "target_trade_count_sum": 35,
      "total_pnl_delta_pct": 0.002369,
      "total_pnl_delta_sum": 591.09,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [
      "window_ev_regression_vs_current_vbb"
    ],
    "gate4_passed": false,
    "max_range_pct": 0.08,
    "max_single_positive_pnl_share": 0.369122,
    "min_dollar_volume": 100000000.0,
    "notional_scalar": 1.1,
    "positive_pnl_hhi": 0.191639,
    "target_trade_count": 35,
    "variant_id": "dvol_gte_100m_range_lte_0p08_scalar_1p10"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.7111,
      "after_total_pnl_sum": 249789.19,
      "baseline_expected_value_score_sum": 8.6861,
      "baseline_total_pnl_sum": 249493.67,
      "expected_value_score_delta_pct": 0.002878,
      "expected_value_score_delta_sum": 0.025,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 35,
      "total_pnl_delta_pct": 0.001184,
      "total_pnl_delta_sum": 295.52,
      "windows_ev_improved": 2,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [
      "window_ev_regression_vs_current_vbb"
    ],
    "gate4_passed": false,
    "max_range_pct": 0.08,
    "max_single_positive_pnl_share": 0.369116,
    "min_dollar_volume": 150000000.0,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.191635,
    "target_trade_count": 35,
    "variant_id": "dvol_gte_150m_range_lte_0p08_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6855,
      "after_total_pnl_sum": 249429.68,
      "baseline_expected_value_score_sum": 8.6861,
      "baseline_total_pnl_sum": 249493.67,
      "expected_value_score_delta_pct": -6.9e-05,
      "expected_value_score_delta_sum": -0.0006,
      "max_drawdown_delta_max": 0.0001,
      "target_trade_count_sum": 24,
      "total_pnl_delta_pct": -0.000256,
      "total_pnl_delta_sum": -63.99,
      "windows_ev_improved": 1,
      "windows_ev_regressed": 2,
      "windows_pnl_improved": 1,
      "windows_pnl_regressed": 2
    },
    "failed_reasons": [
      "aggregate_ev_not_positive_vs_current_vbb",
      "aggregate_pnl_not_positive_vs_current_vbb",
      "window_ev_regression_vs_current_vbb",
      "window_pnl_regression_vs_current_vbb"
    ],
    "gate4_passed": false,
    "max_range_pct": 0.06,
    "max_single_positive_pnl_share": 0.382063,
    "min_dollar_volume": 100000000.0,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.221457,
    "target_trade_count": 24,
    "variant_id": "dvol_gte_100m_range_lte_0p06_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.7146,
      "after_total_pnl_sum": 249949.97,
      "baseline_expected_value_score_sum": 8.6861,
      "baseline_total_pnl_sum": 249493.67,
      "expected_value_score_delta_pct": 0.003281,
      "expected_value_score_delta_sum": 0.0285,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 41,
      "total_pnl_delta_pct": 0.001829,
      "total_pnl_delta_sum": 456.3,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_range_pct": 0.1,
    "max_single_positive_pnl_share": 0.282379,
    "min_dollar_volume": 200000000.0,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.156685,
    "target_trade_count": 41,
    "variant_id": "dvol_gte_200m_range_lte_0p10_scalar_1p05"
  }
]
```

## Cost/Liquidity Audit

```json
{
  "late_strong": {
    "adjusted_dates": [
      "2025-10-29",
      "2025-11-05",
      "2025-11-12",
      "2025-12-10",
      "2025-12-19",
      "2026-01-05",
      "2026-01-06",
      "2026-01-22"
    ],
    "adjusted_dollar_volume_max": 16729139292.33,
    "adjusted_dollar_volume_min": 1766806880.29,
    "adjusted_incremental_pnl": 236.43,
    "adjusted_range_pct_max": 0.077134,
    "adjusted_range_pct_min": 0.023146,
    "adjusted_tickers": [
      "BKNG",
      "CAT",
      "CVX",
      "DIS",
      "LLY",
      "MU"
    ],
    "adjusted_trade_count": 8,
    "all_selected_dollar_volume_max": 16729139292.33,
    "all_selected_dollar_volume_min": 1766806880.29,
    "all_selected_range_pct_max": 0.077134,
    "all_selected_range_pct_min": 0.023146,
    "before_vbb_trade_count": 8,
    "snapshot_ticker_count": 56,
    "unadjusted_trade_count": 0
  },
  "mid_weak": {
    "adjusted_dates": [
      "2025-05-08",
      "2025-05-12",
      "2025-05-14",
      "2025-06-16",
      "2025-06-23",
      "2025-06-26",
      "2025-06-27",
      "2025-06-30",
      "2025-08-06",
      "2025-09-04",
      "2025-09-09",
      "2025-09-16",
      "2025-09-18",
      "2025-09-19",
      "2025-10-01"
    ],
    "adjusted_dollar_volume_max": 47505558007.98,
    "adjusted_dollar_volume_min": 306565158.46,
    "adjusted_incremental_pnl": 137.28,
    "adjusted_range_pct_max": 0.084805,
    "adjusted_range_pct_min": 0.016037,
    "adjusted_tickers": [
      "AMD",
      "AMZN",
      "APP",
      "COIN",
      "CRDO",
      "GE",
      "GS",
      "LLY",
      "MCD",
      "MSFT",
      "SPOT",
      "UNH"
    ],
    "adjusted_trade_count": 15,
    "all_selected_dollar_volume_max": 47505558007.98,
    "all_selected_dollar_volume_min": 306565158.46,
    "all_selected_range_pct_max": 0.112612,
    "all_selected_range_pct_min": 0.016037,
    "before_vbb_trade_count": 17,
    "snapshot_ticker_count": 52,
    "unadjusted_trade_count": 2
  },
  "old_thin": {
    "adjusted_dates": [
      "2024-10-16",
      "2024-10-29",
      "2024-11-01",
      "2024-11-05",
      "2024-11-08",
      "2024-11-21",
      "2024-11-25",
      "2024-12-16",
      "2024-12-20",
      "2025-01-06",
      "2025-01-15",
      "2025-01-17",
      "2025-01-21",
      "2025-01-22",
      "2025-01-28",
      "2025-01-30",
      "2025-02-04",
      "2025-02-28"
    ],
    "adjusted_dollar_volume_max": 65780331265.98,
    "adjusted_dollar_volume_min": 1037304923.11,
    "adjusted_incremental_pnl": 82.59,
    "adjusted_range_pct_max": 0.096663,
    "adjusted_range_pct_min": 0.017582,
    "adjusted_tickers": [
      "AAPL",
      "AMZN",
      "AVGO",
      "COIN",
      "DDOG",
      "DE",
      "GOOG",
      "GS",
      "ISRG",
      "MA",
      "NFLX",
      "PLTR",
      "SNOW",
      "TSLA",
      "TSM",
      "V"
    ],
    "adjusted_trade_count": 18,
    "all_selected_dollar_volume_max": 65780331265.98,
    "all_selected_dollar_volume_min": 142706665.43,
    "all_selected_range_pct_max": 0.143801,
    "all_selected_range_pct_min": 0.017582,
    "before_vbb_trade_count": 22,
    "snapshot_ticker_count": 52,
    "unadjusted_trade_count": 4
  }
}
```

## Production Impact

Replay-only/default-off paper scout unless accepted into shared VBB paper metadata. No live orders, core universe, core ranking, core sizing, exits, LLM/news, or trade-enabled behavior changed.

No JavaScript was used.
