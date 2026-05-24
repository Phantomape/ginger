# exp-20260524-010 SEC 10-Q SPY T+1 Context Notional

Decision: `rejected_sec_10q_spy_context_notional`.

## Best Variant

- best_variant: `tenq_spy_context_scalar_1_50`
- scalar: `1.5`
- metric_gate_passed: `False`
- final_gate_passed: `False`
- EV delta: `0.596267`
- PnL delta: `$12303.14`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.1161 | $+2,779.63 | -0.0012 |
| mid_weak | +0.3802 | $+6,380.01 | -0.0012 |
| old_thin | +0.1000 | $+3,143.50 | +0.0039 |

## Rejection Reason

The best variant failed the numeric SEC paper-sleeve gate on top5_contribution_cap.

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.596267,
    "expected_value_score_sum_delta_pct": 0.050261,
    "max_drawdown_pct_max_delta": 0.003898,
    "max_drawdown_pct_max_delta_pct": 0.033324,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 11992.55,
    "sleeve_total_pnl_sum_delta_pct": 0.137311,
    "total_pnl_sum_delta": 12303.14,
    "total_pnl_sum_delta_pct": 0.037945,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.116075,
      "max_drawdown_pct": -0.001232,
      "sharpe_daily": -0.007539,
      "total_pnl": 2779.63
    },
    "mid_weak": {
      "expected_value_score": 0.380211,
      "max_drawdown_pct": -0.001168,
      "sharpe_daily": 0.11901,
      "total_pnl": 6380.01
    },
    "old_thin": {
      "expected_value_score": 0.099981,
      "max_drawdown_pct": 0.003898,
      "sharpe_daily": 0.0368,
      "total_pnl": 3143.5
    }
  },
  "causal_field_checks": {
    "reason": "`form_base` and `spy_t1_return` are production-visible event/context fields already used by the SEC paper sleeve experiments; the -0.5% SPY T+1 threshold is fixed from prior accepted market-context work.",
    "stable_causal_field": true
  },
  "metric_checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": true,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": false
  },
  "metric_gate_passed": false,
  "metrics": {
    "adjusted_trade_count": 12,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.003898,
    "max_single_positive_pnl_share": 0.313,
    "pnl_hhi_concentration": 0.2043,
    "pnl_top_5_contribution_pct": 0.9207,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
    "production_parity_guard": "Field must be stable event/context data, not archive coverage.",
    "sample_guard": {
      "min_adjusted_trades": 6,
      "min_adjusted_windows": 2
    },
    "tail_guard": {
      "max_hhi_concentration": 0.35,
      "max_single_ticker_positive_share": 0.5,
      "max_top5_contribution": 0.6
    }
  }
}
```

No JavaScript was used.
