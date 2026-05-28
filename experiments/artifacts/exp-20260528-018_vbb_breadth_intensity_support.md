# exp-20260528-018 VBB Breadth-Intensity Support

Decision: `accepted_shared_vbb_breadth_intensity_support`.

Single variable: on top of the accepted exp-20260526-014 VBB paper adapter, selected VBB paper trades receive small default-off paper notional support when same-day volume_breadth_fraction clears the best predeclared threshold.

Best variant: `breadth_fraction_gte_0p25_scalar_1p10`.

## Three-Window Result Versus Exp014

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5780 | 5.6007 | +0.0227 | $121,255.25 | $121,488.20 | $+232.95 | -0.0001 | 2/8 | $+232.95 |
| mid_weak | 2.2780 | 2.2920 | +0.0140 | $80,780.62 | $80,990.62 | $+210.00 | -0.0001 | 5/17 | $+209.99 |
| old_thin | 0.7505 | 0.7613 | +0.0108 | $46,040.62 | $46,424.76 | $+384.14 | -0.0002 | 8/22 | $+384.14 |

## Aggregate

- EV delta vs exp014: `0.0475` (`0.005519`)
- PnL delta vs exp014: `$827.09` (`0.003334`)
- adjusted trades: `15`
- max drawdown drift: `-0.0001`

## Variant Sweep

```json
[
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6502,
      "after_total_pnl_sum": 248740.04,
      "baseline_expected_value_score_sum": 8.6065,
      "baseline_total_pnl_sum": 248076.49,
      "expected_value_score_delta_pct": 0.005078,
      "expected_value_score_delta_sum": 0.0437,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 32,
      "total_pnl_delta_pct": 0.002675,
      "total_pnl_delta_sum": 663.55,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.245875,
    "min_volume_breadth_fraction": 0.18,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.168777,
    "target_trade_count": 32,
    "variant_id": "breadth_fraction_gte_0p18_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6318,
      "after_total_pnl_sum": 248564.08,
      "baseline_expected_value_score_sum": 8.6065,
      "baseline_total_pnl_sum": 248076.49,
      "expected_value_score_delta_pct": 0.00294,
      "expected_value_score_delta_sum": 0.0253,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 23,
      "total_pnl_delta_pct": 0.001965,
      "total_pnl_delta_sum": 487.59,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.328709,
    "min_volume_breadth_fraction": 0.2,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.233926,
    "target_trade_count": 23,
    "variant_id": "breadth_fraction_gte_0p20_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6223,
      "after_total_pnl_sum": 248490.03,
      "baseline_expected_value_score_sum": 8.6065,
      "baseline_total_pnl_sum": 248076.49,
      "expected_value_score_delta_pct": 0.001836,
      "expected_value_score_delta_sum": 0.0158,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 15,
      "total_pnl_delta_pct": 0.001667,
      "total_pnl_delta_sum": 413.54,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.318455,
    "min_volume_breadth_fraction": 0.25,
    "notional_scalar": 1.05,
    "positive_pnl_hhi": 0.269579,
    "target_trade_count": 15,
    "variant_id": "breadth_fraction_gte_0p25_scalar_1p05"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.654,
      "after_total_pnl_sum": 248903.58,
      "baseline_expected_value_score_sum": 8.6065,
      "baseline_total_pnl_sum": 248076.49,
      "expected_value_score_delta_pct": 0.005519,
      "expected_value_score_delta_sum": 0.0475,
      "max_drawdown_delta_max": -0.0001,
      "target_trade_count_sum": 15,
      "total_pnl_delta_pct": 0.003334,
      "total_pnl_delta_sum": 827.09,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [],
    "gate4_passed": true,
    "max_single_positive_pnl_share": 0.318448,
    "min_volume_breadth_fraction": 0.25,
    "notional_scalar": 1.1,
    "positive_pnl_hhi": 0.269581,
    "target_trade_count": 15,
    "variant_id": "breadth_fraction_gte_0p25_scalar_1p10"
  },
  {
    "aggregate": {
      "after_expected_value_score_sum": 8.6496,
      "after_total_pnl_sum": 248632.71,
      "baseline_expected_value_score_sum": 8.6065,
      "baseline_total_pnl_sum": 248076.49,
      "expected_value_score_delta_pct": 0.005008,
      "expected_value_score_delta_sum": 0.0431,
      "max_drawdown_delta_max": 0.0,
      "target_trade_count_sum": 13,
      "total_pnl_delta_pct": 0.002242,
      "total_pnl_delta_sum": 556.22,
      "windows_ev_improved": 3,
      "windows_ev_regressed": 0,
      "windows_pnl_improved": 3,
      "windows_pnl_regressed": 0
    },
    "failed_reasons": [
      "target_concentration_failed"
    ],
    "gate4_passed": false,
    "max_single_positive_pnl_share": 0.424977,
    "min_volume_breadth_fraction": 0.3,
    "notional_scalar": 1.1,
    "positive_pnl_hhi": 0.319018,
    "target_trade_count": 13,
    "variant_id": "breadth_fraction_gte_0p30_scalar_1p10"
  }
]
```

## Gate 4

```json
{
  "aggregate": {
    "after_expected_value_score_sum": 8.654,
    "after_total_pnl_sum": 248903.58,
    "baseline_expected_value_score_sum": 8.6065,
    "baseline_total_pnl_sum": 248076.49,
    "expected_value_score_delta_pct": 0.005519,
    "expected_value_score_delta_sum": 0.0475,
    "max_drawdown_delta_max": -0.0001,
    "target_trade_count_sum": 15,
    "total_pnl_delta_pct": 0.003334,
    "total_pnl_delta_sum": 827.09,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "concentration_passed": true,
  "drawdown_guard": {
    "max_allowed_worse": 0.005,
    "observed_max_delta": -0.0001
  },
  "failed_reasons": [],
  "passed": true,
  "target_trade_summary": {
    "by_ticker_count": {
      "AAPL": 1,
      "AMZN": 1,
      "APP": 2,
      "COIN": 3,
      "CRDO": 1,
      "CVX": 1,
      "DDOG": 1,
      "DE": 2,
      "GS": 1,
      "MU": 1,
      "V": 1
    },
    "by_ticker_pnl": {
      "AAPL": -53.75,
      "AMZN": 5.2,
      "APP": 323.46,
      "COIN": 315.72,
      "CRDO": 136.45,
      "CVX": -1.96,
      "DDOG": -21.22,
      "DE": -18.04,
      "GS": -3.33,
      "MU": 234.91,
      "V": -90.36
    },
    "by_window_pnl": {
      "late_strong": 232.95,
      "mid_weak": 209.99,
      "old_thin": 384.14
    },
    "max_single_positive_pnl_share": 0.318448,
    "positive_by_ticker_pnl": {
      "AMZN": 5.2,
      "APP": 323.46,
      "COIN": 315.72,
      "CRDO": 136.45,
      "MU": 234.91
    },
    "positive_pnl_hhi": 0.269581,
    "total_pnl": 827.08,
    "total_trade_count": 15,
    "windows_with_target_trades": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  }
}
```

## Breadth-Intensity Audit

```json
{
  "late_strong": {
    "adjusted_breadth_fraction_max": 0.684211,
    "adjusted_breadth_fraction_min": 0.289474,
    "adjusted_dates": [
      "2025-12-19",
      "2026-01-05"
    ],
    "adjusted_incremental_pnl": 232.95,
    "adjusted_tickers": [
      "CVX",
      "MU"
    ],
    "adjusted_trade_count": 2,
    "all_selected_breadth_fraction_max": 0.684211,
    "all_selected_breadth_fraction_min": 0.131579,
    "before_vbb_trade_count": 8,
    "snapshot_ticker_count": 56,
    "unadjusted_trade_count": 6
  },
  "mid_weak": {
    "adjusted_breadth_fraction_max": 0.473684,
    "adjusted_breadth_fraction_min": 0.315789,
    "adjusted_dates": [
      "2025-05-12",
      "2025-05-13",
      "2025-06-24",
      "2025-06-27",
      "2025-09-19"
    ],
    "adjusted_incremental_pnl": 209.99,
    "adjusted_tickers": [
      "AMZN",
      "APP",
      "COIN",
      "CRDO"
    ],
    "adjusted_trade_count": 5,
    "all_selected_breadth_fraction_max": 0.473684,
    "all_selected_breadth_fraction_min": 0.131579,
    "before_vbb_trade_count": 17,
    "snapshot_ticker_count": 52,
    "unadjusted_trade_count": 12
  },
  "old_thin": {
    "adjusted_breadth_fraction_max": 0.789474,
    "adjusted_breadth_fraction_min": 0.263158,
    "adjusted_dates": [
      "2024-11-06",
      "2024-11-07",
      "2024-11-25",
      "2024-12-20",
      "2025-01-17",
      "2025-01-21",
      "2025-01-28",
      "2025-02-28"
    ],
    "adjusted_incremental_pnl": 384.14,
    "adjusted_tickers": [
      "AAPL",
      "APP",
      "COIN",
      "DDOG",
      "DE",
      "GS",
      "V"
    ],
    "adjusted_trade_count": 8,
    "all_selected_breadth_fraction_max": 0.789474,
    "all_selected_breadth_fraction_min": 0.131579,
    "before_vbb_trade_count": 22,
    "snapshot_ticker_count": 52,
    "unadjusted_trade_count": 14
  }
}
```

## Production Impact

Replay-only/default-off paper scout. No shared policy, production adapter, run adapter, backtester adapter, watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
