# exp-20260511-114 SEC financial-report exclude 10-K

- Decision: `rejected_exclude_10k_financial_report_t1`
- Changed variable: `sec_financial_report_t1_form_base_eligibility`
- Excluded 10-K rows by window: `{'late_strong': 10, 'mid_weak': 2, 'old_thin': 9}`
- Replay path: accepted max-3 default-off paper sleeve; no live orders.

## Aggregate

| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: |
| include_10k | 6.588843 | $194,441.68 | $8,556.46 | 62 | 0.1188 |
| exclude_10k | 6.482188 | $193,184.12 | $7,298.90 | 60 | 0.1173 |

## Gate

{
  "aggregate_delta": {
    "expected_value_score_sum_delta": -0.106655,
    "expected_value_score_sum_delta_pct": -0.016187,
    "max_drawdown_pct_max_delta": -0.001554,
    "max_drawdown_pct_max_delta_pct": -0.013079,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": -2.0,
    "sleeve_closed_trade_count_sum_delta_pct": -0.032258,
    "sleeve_total_pnl_sum_delta": -1257.56,
    "sleeve_total_pnl_sum_delta_pct": -0.146972,
    "total_pnl_sum_delta": -1257.56,
    "total_pnl_sum_delta_pct": -0.006468,
    "trade_count_sum_delta": -2.0,
    "trade_count_sum_delta_pct": -0.016129
  },
  "ev_positive_windows": 1,
  "ev_regressed_windows": 2,
  "max_drawdown_delta_max": 0.0,
  "passed": false,
  "pnl_positive_windows": 1,
  "rule": "Pass if aggregate EV and sleeve PnL improve, EV improves in at least two windows with zero EV-regression windows, PnL improves in at least two windows, and max drawdown does not worsen.",
  "window_checks": {
    "late_strong": {
      "ev_delta": -0.083289,
      "max_drawdown_delta": 0.0,
      "pnl_delta": -963.39,
      "sleeve_closed_trade_delta": 0
    },
    "mid_weak": {
      "ev_delta": -0.026893,
      "max_drawdown_delta": 0.0,
      "pnl_delta": -457.05,
      "sleeve_closed_trade_delta": -1
    },
    "old_thin": {
      "ev_delta": 0.003527,
      "max_drawdown_delta": -0.001554,
      "pnl_delta": 162.88,
      "sleeve_closed_trade_delta": -1
    }
  }
}

## Production impact

No live orders changed in this replay. If accepted, promote only through shared SEC queue qualification and focused default-off tests; keep the paper sleeve trade-disabled.
