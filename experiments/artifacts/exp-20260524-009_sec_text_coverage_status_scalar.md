# exp-20260524-009 SEC Text-Coverage Status Scalar

Decision: `rejected_sec_missing_text_archive_scalar`.

## Best Variant

- best_variant: `missing_text_scalar_2_00`
- scalar: `2.0`
- metric_gate_passed: `False`
- final_gate_passed: `False`
- EV delta: `1.247804`
- PnL delta: `$26270.17`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.2916 | $+7,339.73 | -0.0024 |
| mid_weak | +0.7979 | $+13,617.00 | -0.0023 |
| old_thin | +0.1582 | $+5,313.44 | +0.0127 |

## Rejection Reason

The best variant improved aggregate EV/PnL across all three windows, but failed the numeric SEC paper-sleeve gate on drawdown_worse_guard, top5_contribution_cap. Keeping it would amplify a tail/concentration pattern before the causal field is production-stable.

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 1.247804,
    "expected_value_score_sum_delta_pct": 0.10518,
    "max_drawdown_pct_max_delta": 0.01272,
    "max_drawdown_pct_max_delta_pct": 0.108745,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 25648.98,
    "sleeve_total_pnl_sum_delta_pct": 0.293673,
    "total_pnl_sum_delta": 26270.17,
    "total_pnl_sum_delta_pct": 0.081022,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.291627,
      "max_drawdown_pct": -0.002417,
      "sharpe_daily": -0.030128,
      "total_pnl": 7339.73
    },
    "mid_weak": {
      "expected_value_score": 0.797947,
      "max_drawdown_pct": -0.00231,
      "sharpe_daily": 0.228471,
      "total_pnl": 13617.0
    },
    "old_thin": {
      "expected_value_score": 0.15823,
      "max_drawdown_pct": 0.01272,
      "sharpe_daily": 0.04856,
      "total_pnl": 5313.44
    }
  },
  "causal_field_checks": {
    "reason": "`missing_text_archive` is a data-coverage/provenance state, not a stable economic or semantic event-quality field. Promoting it would risk production/backtest inconsistency if text coverage changes.",
    "stable_causal_field": false
  },
  "metric_checks": {
    "adjusted_trade_sample": true,
    "adjusted_window_coverage": true,
    "drawdown_worse_guard": false,
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
    "adjusted_trade_count": 16,
    "adjusted_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_drawdown_worse": 0.01272,
    "max_single_positive_pnl_share": 0.2873,
    "pnl_hhi_concentration": 0.1792,
    "pnl_top_5_contribution_pct": 0.848,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
    "production_parity_guard": "Field must be stable economic/semantic context, not data availability.",
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
