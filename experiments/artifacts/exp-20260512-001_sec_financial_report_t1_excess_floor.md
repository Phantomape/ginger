# exp-20260512-001 SEC financial-report T+1 excess floor

- Decision: `accepted_default_off_t1_excess_floor`
- Changed variable: `sec_financial_report_t1_excess_return_floor`
- Best floor: `0.01`
- Replay path: accepted max-3 default-off paper sleeve; no live orders.

## Aggregate

| Variant | Floor | Candidates | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| floor_0.0000 | 0.0000 | 164 | 6.588843 | $194,441.68 | $8,556.46 | 62 | 0.1188 |
| floor_0.0025 | 0.0025 | 152 | 6.777526 | $194,622.71 | $8,737.49 | 60 | 0.1335 |
| floor_0.0050 | 0.0050 | 140 | 7.004711 | $198,335.69 | $12,450.47 | 58 | 0.1335 |
| floor_0.0100 | 0.0100 | 108 | 7.409199 | $209,889.79 | $24,004.57 | 52 | 0.0907 |
| floor_0.0150 | 0.0150 | 90 | 7.018941 | $203,043.00 | $17,157.78 | 46 | 0.0912 |
| floor_0.0200 | 0.0200 | 68 | 6.614369 | $192,960.05 | $7,074.83 | 43 | 0.0919 |
| floor_0.0300 | 0.0300 | 44 | 7.264453 | $199,286.04 | $13,814.94 | 30 | 0.0924 |

## Gate

{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.820356,
    "expected_value_score_sum_delta_pct": 0.124507,
    "max_drawdown_pct_max_delta": -0.028109,
    "max_drawdown_pct_max_delta_pct": -0.236584,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": -10.0,
    "sleeve_closed_trade_count_sum_delta_pct": -0.16129,
    "sleeve_total_pnl_sum_delta": 15448.11,
    "sleeve_total_pnl_sum_delta_pct": 1.805432,
    "total_pnl_sum_delta": 15448.11,
    "total_pnl_sum_delta_pct": 0.079449,
    "trade_count_sum_delta": -10.0,
    "trade_count_sum_delta_pct": -0.080645
  },
  "ev_positive_windows": 3,
  "ev_regressed_windows": 0,
  "max_drawdown_delta_max": -0.000278,
  "passed": true,
  "pnl_positive_windows": 3,
  "rule": "Pass if aggregate EV and sleeve PnL improve, EV improves in at least two windows with at most one EV-regression window, PnL improves in at least two windows, max drawdown worsens by no more than 0.5 percentage points, and the sleeve keeps at least 40 closed trades.",
  "sleeve_closed_trade_count_after": 52,
  "window_checks": {
    "late_strong": {
      "ev_delta": 0.281744,
      "max_drawdown_delta": -0.00495,
      "pnl_delta": 2782.53,
      "sleeve_closed_trade_delta": -5
    },
    "mid_weak": {
      "ev_delta": 0.352094,
      "max_drawdown_delta": -0.000278,
      "pnl_delta": 5858.06,
      "sleeve_closed_trade_delta": -3
    },
    "old_thin": {
      "ev_delta": 0.186518,
      "max_drawdown_delta": -0.029431,
      "pnl_delta": 6807.52,
      "sleeve_closed_trade_delta": -2
    }
  }
}

## Production impact

No live orders changed in this replay. If accepted, promote only by changing the shared SEC financial-report queue qualification constant plus focused default-off tests.
