# exp-20260512-002 SEC financial-report hold days

- Decision: `rejected_hold_days`
- Changed variable: `sec_financial_report_event_sleeve_hold_days`
- Best hold days: `12`
- Replay path: accepted max-3 and T+1 excess >=1% default-off paper sleeve; no live orders.

## Aggregate

| Variant | Hold days | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hold_5d | 5 | 6.778114 | $203,648.45 | $17,763.23 | 67 | 0.0931 |
| hold_7d | 7 | 6.601393 | $198,440.82 | $12,555.60 | 60 | 0.0924 |
| hold_10d | 10 | 7.409199 | $209,889.79 | $24,004.57 | 52 | 0.0907 |
| hold_12d | 12 | 7.282695 | $207,184.38 | $21,522.68 | 44 | 0.0898 |
| hold_15d | 15 | 6.625012 | $194,863.63 | $9,068.23 | 40 | 0.0982 |
| hold_20d | 20 | 7.393241 | $211,588.69 | $25,793.29 | 37 | 0.0896 |

## Gate

{
  "aggregate_delta": {
    "expected_value_score_sum_delta": -0.126504,
    "expected_value_score_sum_delta_pct": -0.017074,
    "max_drawdown_pct_max_delta": -0.00094,
    "max_drawdown_pct_max_delta_pct": -0.010363,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": -8.0,
    "sleeve_closed_trade_count_sum_delta_pct": -0.153846,
    "sleeve_total_pnl_sum_delta": -2481.89,
    "sleeve_total_pnl_sum_delta_pct": -0.103392,
    "total_pnl_sum_delta": -2705.41,
    "total_pnl_sum_delta_pct": -0.01289,
    "trade_count_sum_delta": -8.0,
    "trade_count_sum_delta_pct": -0.070175
  },
  "ev_positive_windows": 1,
  "ev_regressed_windows": 2,
  "max_drawdown_delta_max": -0.000234,
  "passed": false,
  "pnl_positive_windows": 1,
  "rule": "Pass if aggregate EV and sleeve PnL improve, EV improves in at least two windows with at most one EV regression, PnL improves in at least two windows, max drawdown worsens by no more than 0.5 percentage points, and the sleeve keeps at least 40 closed trades.",
  "sleeve_closed_trade_count_after": 44,
  "window_checks": {
    "late_strong": {
      "ev_delta": 0.001618,
      "max_drawdown_delta": -0.000234,
      "pnl_delta": 261.08,
      "sleeve_closed_trade_delta": -2
    },
    "mid_weak": {
      "ev_delta": -0.078934,
      "max_drawdown_delta": -0.00094,
      "pnl_delta": -1359.95,
      "sleeve_closed_trade_delta": -3
    },
    "old_thin": {
      "ev_delta": -0.049188,
      "max_drawdown_delta": -0.001126,
      "pnl_delta": -1606.54,
      "sleeve_closed_trade_delta": -3
    }
  }
}

## Production impact

No live orders changed. If accepted, promote only by changing the shared default-off paper sleeve hold-days config and adding a focused no-orders lifecycle test.
