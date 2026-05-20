# exp-20260520-008 SEC Positive-Language Low-Reaction Notional

Decision: `rejected_sec_positive_language_low_reaction_notional`.

## Hypothesis

Within the SEC financial-report default-off paper sleeve, covered positive_language rows with muted T+1 excess reaction may be underreaction candidates. A bounded paper-notional scalar may improve allocation without changing queue eligibility, hold days, capacity, or live orders.

## Best Variant

- best_variant: `positive_low_reaction_scalar_0_00`
- target_scalar: `0.0`
- EV delta: `0.049637`
- PnL delta: `$1315.95`
- gate_passed: `False`

## Three-Window Deltas

| Window | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|
| late_strong | +0.0000 | $+0.00 | +0.0000 |
| mid_weak | +0.0000 | $+0.00 | +0.0000 |
| old_thin | +0.0496 | $+1,315.95 | -0.0006 |

## Gate

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.049637,
    "expected_value_score_sum_delta_pct": 0.004184,
    "max_drawdown_pct_max_delta": -0.000627,
    "max_drawdown_pct_max_delta_pct": -0.00536,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 1315.95,
    "sleeve_total_pnl_sum_delta_pct": 0.015067,
    "total_pnl_sum_delta": 1315.95,
    "total_pnl_sum_delta_pct": 0.004059,
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
      "expected_value_score": 0.049637,
      "max_drawdown_pct": -0.000627,
      "sharpe_daily": 0.024912,
      "total_pnl": 1315.95
    }
  },
  "checks": {
    "adjusted_trade_sample": false,
    "adjusted_window_coverage": false,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "hhi_concentration_cap": false,
    "no_ev_regressed_windows": true,
    "positive_aggregate_ev": true,
    "positive_aggregate_pnl": true,
    "single_ticker_positive_share_cap": false,
    "top5_contribution_cap": false
  },
  "metrics": {
    "adjusted_trade_count": 1,
    "adjusted_windows": [
      "old_thin"
    ],
    "max_drawdown_worse": 0.0,
    "max_single_positive_pnl_share": 1.0,
    "pnl_hhi_concentration": 1.0,
    "pnl_top_5_contribution_pct": 1.0,
    "windows_ev_improved": 1,
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
  "adjusted_trade_count": 1,
  "by_ticker_count": {
    "TSLA": 1
  },
  "by_ticker_incremental_pnl": {
    "TSLA": 1315.95
  },
  "by_window_count": {
    "old_thin": 1
  },
  "by_window_incremental_pnl": {
    "old_thin": 1315.95
  },
  "max_single_positive_incremental_pnl": 1315.95,
  "max_single_positive_pnl_share": 1.0,
  "pnl_hhi_concentration": 1.0,
  "pnl_top_5_contribution_pct": 1.0,
  "positive_by_ticker_incremental_pnl": {
    "TSLA": 1315.95
  },
  "positive_incremental_pnl": 1315.95,
  "sample_rows": [
    {
      "adjusted_pnl": -0.0,
      "baseline_pnl": -1315.95,
      "entry_date": "2025-02-03",
      "event_family": "earnings_8k",
      "event_notional_rule": "base+positive_language_low_reaction_scalar",
      "event_notional_scalar": 0.0,
      "exit_date": "2025-02-18",
      "form_base": "8-K",
      "incremental_pnl": 1315.95,
      "language_bucket": "positive_language",
      "notional": 0.0,
      "spy_t1_return": -0.005322,
      "t1_excess_return_vs_spy": 0.016114,
      "t1_return": 0.010792,
      "text_event_type": "earnings_release_text",
      "ticker": "TSLA",
      "window": "old_thin"
    }
  ],
  "windows_present": 1
}
```

No JavaScript was used.
