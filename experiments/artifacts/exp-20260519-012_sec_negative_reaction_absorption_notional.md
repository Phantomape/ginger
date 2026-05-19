# exp-20260519-012 SEC Negative-Reaction Absorption Notional

Decision: `rejected_sec_negative_reaction_absorption_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered negative_language rows whose first T+1 reaction underperforms SPY may be absorption/reversal candidates. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `negative_reaction_scalar_0_00`
- target_scalar: `0.0`
- EV delta: `0.0`
- PnL delta: `$0.0`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 |
| old_thin | +0.0000 | $+0.00 | +0.0000 |

## Gate

```json
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
  "by_window": {
    "late_strong": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "mid_weak": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "total_pnl": 0.0
    }
  },
  "checks": {
    "adjusted_trade_sample": false,
    "adjusted_window_coverage": false,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": true,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": false,
    "positive_aggregate_pnl": false,
    "single_ticker_positive_share_cap": true,
    "top5_contribution_cap": true
  },
  "metrics": {
    "adjusted_trade_count": 0,
    "adjusted_windows": [],
    "max_drawdown_worse": 0.0,
    "max_single_positive_pnl_share": null,
    "pnl_hhi_concentration": null,
    "pnl_top_5_contribution_pct": null,
    "windows_ev_improved": 0,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "rules": {
    "metric_gate": "aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, and max drawdown worsening <= 0.5pp",
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

## Selection

```json
{
  "adjusted_trade_count": 0,
  "by_ticker_count": {},
  "by_ticker_incremental_pnl": {},
  "by_window_count": {},
  "by_window_incremental_pnl": {},
  "max_single_positive_incremental_pnl": 0.0,
  "max_single_positive_pnl_share": null,
  "pnl_hhi_concentration": null,
  "pnl_top_5_contribution_pct": null,
  "positive_by_ticker_incremental_pnl": {},
  "positive_incremental_pnl": 0.0,
  "sample_rows": [],
  "windows_present": 0
}
```

No JavaScript was used.
