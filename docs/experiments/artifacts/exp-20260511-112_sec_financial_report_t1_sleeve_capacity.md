# exp-20260511-112 SEC financial-report T+1 sleeve capacity

- Decision: `accept_default_off_paper_capacity_candidate`
- Changed variable: `sec_financial_report_event_sleeve_max_positions`
- Before: max_positions=1; after candidate: max_positions=3
- Replay path: production `build_sec_financial_report_event_sleeve_snapshot`, persist disabled.

## Aggregate

| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: |
| max_positions_1 | 6.414058 | $187,675.61 | $2,204.51 | 26 | 0.0926 |
| max_positions_2 | 6.601904 | $190,996.36 | $5,318.20 | 47 | 0.0927 |
| max_positions_3 | 6.588843 | $194,441.68 | $8,556.46 | 62 | 0.1188 |
| max_positions_5 | 6.832118 | $201,770.62 | $15,614.80 | 87 | 0.1434 |
| max_positions_10 | 7.137317 | $205,503.24 | $19,347.42 | 124 | 0.1571 |

## Gate

{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.174785,
    "expected_value_score_sum_delta_pct": 0.02725,
    "max_drawdown_pct_max_delta": 0.026213,
    "max_drawdown_pct_max_delta_pct": 0.283081,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 36.0,
    "sleeve_closed_trade_count_sum_delta_pct": 1.384615,
    "sleeve_total_pnl_sum_delta": 6351.95,
    "sleeve_total_pnl_sum_delta_pct": 2.881343,
    "total_pnl_sum_delta": 6766.07,
    "total_pnl_sum_delta_pct": 0.036052,
    "trade_count_sum_delta": 36.0,
    "trade_count_sum_delta_pct": 0.409091
  },
  "ev_positive_windows": 2,
  "max_drawdown_delta_max": 0.033416,
  "passed": true,
  "pnl_positive_windows": 3,
  "rule": "Pass if aggregate EV improves, sleeve PnL delta >= $5k, PnL improves in all three windows, EV improves in at least two windows, and no window adds more than 5 percentage points of drawdown.",
  "window_checks": {
    "late_strong": {
      "ev_delta": -0.013675,
      "max_drawdown_delta": 0.001699,
      "pnl_delta": 1055.0
    },
    "mid_weak": {
      "ev_delta": 0.09226,
      "max_drawdown_delta": -0.001618,
      "pnl_delta": 1578.4
    },
    "old_thin": {
      "ev_delta": 0.0962,
      "max_drawdown_delta": 0.033416,
      "pnl_delta": 4132.67
    }
  }
}

## Production impact

Promotion applied to the shared default-off paper sleeve config: `DEFAULT_MAX_POSITIONS=3`. `run.py` consumes the same production sleeve builder, `trade_enabled` remains false, and no live orders or core signal path changed.
