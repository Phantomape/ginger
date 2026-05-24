# exp-20260524-016 Core-Misfit Trend Long Risk Haircut

Decision: `rejected_core_misfit_trend_long_risk_haircut`.

## Hypothesis
The established CORE_MISFIT_PAPER ticker set may be negative for core long exposure but too blunt for a hard no-entry rule. A bounded post-sizing risk haircut for TSM/ISRG/V/DDOG trend_long signals may improve EV by reducing the known drag while preserving some participation and avoiding replacement-slot side effects.

## Three-Window Aggregate
- baseline EV: `7.8941`
- best EV: `7.8938`
- EV delta: `-0.0003`
- PnL delta: `$-30.32`

## Sweep Summary
| variant | multiplier | EV delta | PnL delta | DD delta | changed trades | max pos share | HHI | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| misfit_trend_risk_025 | 0.25 | -0.0003 | -30.32 | 0.0 | 4 | 0.8718 | 0.7714 | False |
| misfit_trend_risk_050 | 0.5 | -0.0334 | -1221.52 | 0.0 | 5 | 0.8664 | 0.762 | False |
| misfit_trend_risk_075 | 0.75 | -0.06 | -2276.6 | 0.0 | 5 | 0.8617 | 0.7537 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival |
|---|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0003 | 9.27 | 0.0 | 0.0 |
| old_thin | -0.0006 | -39.59 | -0.0107 | 0.0166 |

## Gate 4
```json
{
  "aggregate_delta": {
    "expected_value_score_sum": -0.0003,
    "max_drawdown_pct_max": 0.0,
    "min_survival_rate": 0.0,
    "total_pnl_sum": -30.32,
    "trade_count_sum": -2.0
  },
  "by_window_delta": {
    "late_strong": {
      "converged": 0.0,
      "expected_value_score": 0.0,
      "max_consecutive_losses": 0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "signals_generated": 0,
      "signals_survived": 0,
      "survival_rate": 0.0,
      "tail_loss_share": 0.0,
      "total_pnl": 0.0,
      "total_return_pct": 0.0,
      "trade_count": 0,
      "win_rate": 0.0,
      "worst_trade_pct": 0.0
    },
    "mid_weak": {
      "converged": 0.0,
      "expected_value_score": 0.0003,
      "max_consecutive_losses": 0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "signals_generated": 0,
      "signals_survived": 0,
      "survival_rate": 0.0,
      "tail_loss_share": 0.002991,
      "total_pnl": 9.27,
      "total_return_pct": 0.0001,
      "trade_count": -1,
      "win_rate": 0.0262,
      "worst_trade_pct": 0.0
    },
    "old_thin": {
      "converged": 0.0,
      "expected_value_score": -0.0006,
      "max_consecutive_losses": 0,
      "max_drawdown_pct": -0.0107,
      "sharpe_daily": 0.0,
      "signals_generated": 0,
      "signals_survived": 1,
      "survival_rate": 0.0166,
      "tail_loss_share": 0.031316,
      "total_pnl": -39.59,
      "total_return_pct": -0.0004,
      "trade_count": -1,
      "win_rate": 0.0195,
      "worst_trade_pct": 0.004478
    }
  },
  "checks": {
    "changed_trade_sample": true,
    "drawdown_worse_guard": true,
    "ev_improved_window_coverage": false,
    "no_ev_regressed_windows": false,
    "positive_aggregate_ev": false,
    "positive_aggregate_pnl": false,
    "positive_pnl_hhi_cap": false,
    "single_positive_ticker_share_cap": false,
    "survival_guard": true,
    "target_trade_sample": true,
    "target_window_sample": true
  },
  "improved_windows": [
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0,
  "passed": false,
  "regressed_windows": [
    "old_thin"
  ],
  "rules": {
    "max_drawdown_worse": 0.005,
    "max_ev_regressed_windows": 0,
    "max_positive_pnl_hhi": 0.45,
    "max_single_positive_ticker_share": 0.5,
    "min_changed_trades": 3,
    "min_ev_improved_windows": 2,
    "min_target_trades": 3,
    "min_target_windows": 2
  }
}
```

## Production Impact
No shared production policy, run adapter, backtester adapter, watchlist, or order path changed. If accepted later, this must move into shared sizing policy with parity tests before order behavior changes.

No JavaScript was used.
