# exp-20260511-113 SEC financial-report pending quality ranking

- Decision: `rejected_pending_quality_rank`
- Changed variable: `sec_financial_report_pending_fill_priority`
- Baseline: pending entries fill by created date first, then T+1 excess.
- Variant: pending entries fill by T+1 excess first, then created date.
- Replay path: production `build_sec_financial_report_event_sleeve_snapshot`, persist disabled.

## Aggregate

| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: |
| age_first_t1_excess | 6.588843 | $194,441.68 | $8,556.46 | 62 | 0.1188 |
| quality_first_t1_excess | 6.588843 | $194,441.68 | $8,556.46 | 62 | 0.1188 |

## Gate

{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.0,
    "expected_value_score_sum_delta_pct": 0.0,
    "max_drawdown_pct_max_delta": 0.0,
    "max_drawdown_pct_max_delta_pct": 0.0,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 0.0,
    "sleeve_total_pnl_sum_delta_pct": 0.0,
    "total_pnl_sum_delta": 0.0,
    "total_pnl_sum_delta_pct": 0.0,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "ev_positive_windows": 0,
  "ev_regressed_windows": 0,
  "max_drawdown_delta_max": 0.0,
  "passed": false,
  "pnl_positive_windows": 0,
  "rule": "Pass if aggregate EV improves, sleeve PnL delta >= $2.5k, EV improves in at least two windows with zero EV-regression windows, PnL improves in at least two windows, and no window adds more than 2 percentage points of drawdown.",
  "window_checks": {
    "late_strong": {
      "closed_trade_delta": 0,
      "ev_delta": 0.0,
      "max_drawdown_delta": 0.0,
      "pnl_delta": 0.0
    },
    "mid_weak": {
      "closed_trade_delta": 0,
      "ev_delta": 0.0,
      "max_drawdown_delta": 0.0,
      "pnl_delta": 0.0
    },
    "old_thin": {
      "closed_trade_delta": 0,
      "ev_delta": 0.0,
      "max_drawdown_delta": 0.0,
      "pnl_delta": 0.0
    }
  }
}

## Production impact

No live orders changed. If accepted, the change must be promoted only by changing the shared default-off paper sleeve pending sort helper and by adding a focused no-orders ranking test.
