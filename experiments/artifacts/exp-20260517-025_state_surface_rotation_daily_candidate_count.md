# exp-20260517-025 State-Surface Rotation Daily Candidate Count

Decision: `accepted_shared_default_off_policy_daily_candidate_count`.

Single causal variable: `daily_candidate_count` for the default-off rotation-only state-surface paper sleeve.

## Sweep

| Daily count | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | FAIL | -0.1573 | $-3,974.41 | 2 | 1 | 15 | +0.3400% | 29.27% |
| 2 | FAIL | -0.3094 | $-890.79 | 1 | 2 | 20 | +0.2800% | 29.31% |
| 3 | FAIL | +0.0000 | $+0.00 | 0 | 0 | 22 | +0.0000% | 29.72% |
| 4 | PASS | +0.3987 | $+5,296.50 | 2 | 0 | 23 | +0.1300% | 34.07% |
| 5 | PASS | +0.3995 | $+5,321.49 | 2 | 0 | 24 | +0.1300% | 34.04% |
| 6 | PASS | +0.3995 | $+5,321.49 | 2 | 0 | 24 | +0.1300% | 34.04% |

## Three-Window Best Variant

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.4537 | 5.6541 | +0.2004 | $123,387.98 | $125,367.73 | $+1,979.75 | 6.22% | 6.35% | 9 |
| mid_weak | 2.8498 | 3.0489 | +0.1991 | $90,469.80 | $93,811.54 | $+3,341.74 | 10.83% | 10.83% | 12 |
| old_thin | 0.8626 | 0.8626 | +0.0000 | $49,572.69 | $49,572.69 | $+0.00 | 9.40% | 9.40% | 3 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.3995,
  "aggregate_pnl_delta": 5321.49,
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0013,
      "ev_delta_pct": 0.036746,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.016045,
      "sharpe_daily_delta": 0.09,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.069865,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": true,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.036938,
      "sharpe_daily_delta": 0.1,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.0,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.0,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "concentration_guard_passed": true,
  "delta_metrics": {
    "after_ev_sum": 9.5656,
    "after_pnl_sum": 268751.96,
    "aggregate_ev_delta": 0.3995,
    "aggregate_ev_delta_pct": 0.043585,
    "aggregate_pnl_delta": 5321.49,
    "aggregate_pnl_delta_pct": 0.020201,
    "baseline_ev_sum": 9.1661,
    "baseline_pnl_sum": 263430.47,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.2004,
        "max_drawdown_pct": 0.0013,
        "sharpe_daily": 0.09,
        "survival_rate": 0.0,
        "total_pnl": 1979.75,
        "total_return_pct": 0.0198,
        "trade_count": 0.0,
        "win_rate": 0.0371
      },
      "mid_weak": {
        "expected_value_score": 0.1991,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.1,
        "survival_rate": 0.0,
        "total_pnl": 3341.74,
        "total_return_pct": 0.0334,
        "trade_count": 2.0,
        "win_rate": 0.0235
      },
      "old_thin": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "by_window_max_drawdown_delta": {
      "late_strong": 0.0013,
      "mid_weak": 0.0,
      "old_thin": 0.0
    },
    "max_drawdown_worse_max": 0.0013,
    "windows_ev_improved": 2,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 2,
    "windows_pnl_regressed": 0
  },
  "drawdown_guard_passed": true,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0013,
  "max_single_ticker_positive_share": 0.5,
  "minimum_selected_trades": 9,
  "passed": true,
  "sample_guard_passed": true,
  "selected_trade_count": 24,
  "single_ticker_positive_share": 0.340442,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0
}
```

No JavaScript was used.
